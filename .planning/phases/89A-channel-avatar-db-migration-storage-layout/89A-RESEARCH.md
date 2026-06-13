# Phase 89A: Channel-Avatar DB Migration + Storage Layout - Research

**Researched:** 2026-06-13
**Domain:** SQLite additive migration + path accessor + eager directory creation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Directory created **eagerly** in `assets.py:ensure_dirs()` via `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`.
- **D-02:** Expose path via a dedicated `paths.channel_avatars_dir()` returning `os.path.join(_root(), "assets", "channel-avatars")`, mirroring `assets_dir()`. Must respect `_root_override`.
- **D-03:** Flat layout — `assets/channel-avatars/<station-id>.png`. Column stores path relative to `data_dir()`, e.g. `assets/channel-avatars/12.png`.
- **D-04:** Add column using the idempotent try/except `OperationalError` idiom in `db_init()`.
- **D-05:** ALTER TABLE MUST land **after** the `stations_new` rebuild block (~L208–265).
- **D-06:** Migration + directory ONLY in this phase. Do NOT thread `channel_avatar_path` through `Station` dataclass, row mappers, or `save_station()`.
- **D-07:** Migration test proves (a) idempotency (double `db_init()` no raise + schema unchanged) and (b) schema convergence: fresh DB and upgraded (pre-89a) DB produce identical `PRAGMA table_info(stations)`.

### Claude's Discretion

- Exact test file location and fixture style (follow existing `repo.py` migration tests).
- Whether `ensure_dirs()` gets one combined makedirs block or a separate line — match surrounding style.
- Inline comment wording for the new ALTER (mirror Phase 82/83 comments).

### Deferred Ideas (OUT OF SCOPE)

- Threading `channel_avatar_path` through `Station` dataclass, row mappers, `save_station()` — Phase 89.
- `yt_import.fetch_channel_avatar()` and YouTube cover-slot swap — Phase 89.
- Twitch Helix `profile_image_url` fetch — Phase 89b.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-AVATAR-01 | `stations` table gains a `channel_avatar_path TEXT` column via idempotent additive migration in `repo.py:db_init()`; existing rows default to NULL | Confirmed idiom at repo.py L274–311; exact anchor point identified post-L311 |
| ART-AVATAR-02 | New filesystem directory `~/.local/share/musicstreamer/assets/channel-avatars/` stores avatar PNGs keyed by station ID | Confirmed `ensure_dirs()` shape (assets.py L7–9); `assets_dir()` accessor template (paths.py L42–43) |
</phase_requirements>

---

## Summary

Phase 89A is a pure schema + directory bootstrapping change. Every implementation move is a copy-and-adapt of patterns that are already present, tested, and working in the codebase. The additive migration idiom (`try: ALTER TABLE ... ADD COLUMN / except sqlite3.OperationalError: pass`) appears four times in `repo.py` (for `cover_art_source`, `preferred_stream_id`, `prerolls_fetched_at`, and earlier columns at L164–198); the Phase 89A block will be the fifth and slots in immediately after line 311. The paths accessor pattern appears unchanged through `paths.py:assets_dir()` at L42–43, and `ensure_dirs()` at `assets.py:L7–9` is two lines — the new `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)` is a third. No new packages, no new concepts, no external dependencies.

The most important planning input is the Validation Architecture section: the existing repo tests define the exact fixture style and PRAGMA assertion shape that the idempotency + schema-convergence test (D-07) must mirror. Tests live in `tests/test_repo.py` and follow the `repo` fixture (lines 6–13 of that file) for fresh-DB tests and a `_make_bare_con()` helper (L620–624) for pre-migration schema tests.

**Primary recommendation:** Implement in three atomic steps — (1) add `channel_avatars_dir()` to `paths.py`, (2) append `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)` to `ensure_dirs()` in `assets.py`, (3) append the new ALTER block to `db_init()` in `repo.py` after L311 — then write the two new tests to `tests/test_repo.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DB schema migration | Database / Storage (`repo.py:db_init`) | — | All schema bootstrapping goes through `db_init`; no ORM, direct sqlite3 |
| Storage path resolution | Path module (`paths.py`) | — | Pure module, single source of truth; `_root_override` makes it test-friendly |
| Directory creation at startup | Startup (`assets.py:ensure_dirs`) | — | Eager creation on first run; called by `__main__.py` before any writes |
| Column value shape (relative path) | Convention, not code | — | D-03 locks the shape; Phase 89 will write values using `copy_asset_for_station` precedent |

---

## Standard Stack

No new external packages in this phase. All dependencies already present.

### Core (existing)

| Module | Role | Already Used |
|--------|------|-------------|
| `sqlite3` (stdlib) | DB connection, `ALTER TABLE`, `PRAGMA table_info` | Yes — all of `repo.py` |
| `os` (stdlib) | `os.makedirs`, `os.path.join` | Yes — `assets.py`, `paths.py` |
| `platformdirs` | `user_data_dir("musicstreamer")` → `_root()` | Yes — `paths.py:L31` |

### Package Legitimacy Audit

No external packages installed in this phase. Section not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Application startup
       |
       v
  assets.ensure_dirs()                     paths.channel_avatars_dir()
  [assets.py L7-9 + new L10]  ---------> returns _root()/"assets"/"channel-avatars"
       |                                          |
       v                                         v
  os.makedirs(..., exist_ok=True)        ~/.local/share/musicstreamer/
       |                                 └─ assets/
       |                                    └─ channel-avatars/   <-- new
       |
       v
  repo.db_init(con)                     stations table
  [repo.py L88-311 + new block]  ----> channel_avatar_path TEXT (NULL)
       |                                (all existing rows NULL — additive)
       v
  Idempotent on second call
  (OperationalError swallowed)
```

### Recommended Project Structure (no new directories needed)

The three changes land in existing files:

```
musicstreamer/
├── paths.py        + channel_avatars_dir() after eq_profiles_dir() (L94-101)
├── assets.py       + one makedirs line in ensure_dirs() (after current L9)
└── repo.py         + ALTER TABLE block after L311 (after Phase 83 block)

tests/
└── test_repo.py    + two new test functions (idempotency + schema convergence)
```

### Pattern 1: Additive Migration Idiom (confirmed from repo.py)

**What:** Wrap `ALTER TABLE ... ADD COLUMN` in a try/except to make repeated `db_init()` safe.  
**When to use:** Every time a new column is added post-initial-schema.

```python
# repo.py L274-280 (Phase 73 — closest analog for a nullable column with no DEFAULT):
# Phase 82 D-01/D-08 — per-station sticky preferred stream FK.
# MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
# rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
# dynamically-added columns, so placing the ALTER here ensures the column
# lands on the rebuilt (or fresh) table. Nullable INTEGER with no DEFAULT
# (D-01 — NULL means no preference set; no backfill needed). Idempotent
# via the same try/except sqlite3.OperationalError idiom as above.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN preferred_stream_id INTEGER REFERENCES station_streams(id) ON DELETE SET NULL"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

**For Phase 89A the new block (to go at L312+):**

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

[VERIFIED: read from musicstreamer/repo.py L267–311]

### Pattern 2: Path Accessor (confirmed from paths.py)

**What:** Pure function returning `os.path.join(_root(), ...)`. Respects `_root_override` automatically because `_root()` does.  
**When to use:** Every new on-disk location.

```python
# paths.py L42-43 (assets_dir — the direct template for channel_avatars_dir):
def assets_dir() -> str:
    return os.path.join(_root(), "assets")

# New accessor to add (mirrors eq_profiles_dir shape at L94-101):
def channel_avatars_dir() -> str:
    """Phase 89A D-02: flat directory for per-station channel avatar PNGs.

    Pure — does NOT create the directory. Callers use
    ``os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`` before writing.
    Respects ``_root_override`` via ``_root()`` for test isolation.
    """
    return os.path.join(_root(), "assets", "channel-avatars")
```

[VERIFIED: read from musicstreamer/paths.py L42–43, L94–101]

### Pattern 3: ensure_dirs() eager makedirs (confirmed from assets.py)

**Current shape (assets.py L7–9):**

```python
def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
```

**After Phase 89A (append a third line matching the style):**

```python
def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
    os.makedirs(paths.channel_avatars_dir(), exist_ok=True)
```

[VERIFIED: read from musicstreamer/assets.py L7–9]

### Anti-Patterns to Avoid

- **Hardcoding the path string in assets.py or repo.py:** Every path must go through `paths.channel_avatars_dir()` — zero duplicated string literals. If the base changes, it changes in one place.
- **Placing the ALTER TABLE before the `stations_new` rebuild block:** See Pitfall 1 below. The rebuild at L208–265 drops all dynamically-added columns.
- **Threading `channel_avatar_path` into `Station` dataclass in this phase:** D-06 explicitly forbids it. Keep the column DB-only until Phase 89.
- **Using `os.makedirs` without `exist_ok=True`:** Will raise `FileExistsError` on second startup.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent column add | Custom schema version table | `try: ALTER TABLE / except OperationalError: pass` | Already in repo; proven across 4 migrations; no extra state |
| Cross-platform data root | Hardcoded `~/.local/share/musicstreamer` | `paths._root()` via `platformdirs` | Works on Windows/macOS without change; tests override via `_root_override` |
| Directory existence check before makedirs | `if not os.path.exists(d): os.makedirs(d)` | `os.makedirs(d, exist_ok=True)` | Atomic; no TOCTOU race |

---

## Common Pitfalls

### Pitfall 1 (Pitfall 2 in CONTEXT.md): Rebuild-Ordering Trap — ALTER Before the `stations_new` Block

**What goes wrong:** If the new `ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT` block is placed anywhere *before* L208 (the `stations_new` rebuild block), the rebuild will silently drop the column. The rebuild's `CREATE TABLE stations_new` DDL and `INSERT INTO stations_new ... SELECT ...` at L244–248 explicitly enumerate only the columns they know about. Any column added before the rebuild via ALTER is not carried over.

**Why it happens:** SQLite `INSERT INTO ... SELECT` maps by position/name only from the `stations_new` DDL; it has no `SELECT *` that would capture dynamic columns.

**How to avoid:** The new ALTER block must land **after** line 311 (the end of the Phase 83 `prerolls_fetched_at` block). All three existing post-rebuild ALTERs (Phase 73 at L274, Phase 82 at L289, Phase 83 at L305) are correctly placed after L265. Follow the same convention and cite Pitfall 2 in the inline comment.

**Warning signs:** If you see the ALTER before the `except sqlite3.OperationalError: pass  # url column already gone` at L264, it is in the wrong place.

[VERIFIED: read from musicstreamer/repo.py L208–311]

### Pitfall 2: Test Using Real `~/.local/share/musicstreamer` Instead of `tmp_path`

**What goes wrong:** A test that does not set `paths._root_override` will create the real `channel-avatars/` directory and write to the real DB during the test run.

**Why it happens:** `paths._root()` defaults to `platformdirs.user_data_dir("musicstreamer")` unless `_root_override` is set.

**How to avoid:** Every test that touches the filesystem or calls `db_init()` must either use the `repo` fixture (which calls `db_init` on a `tmp_path`-based connection) or set `paths._root_override = str(tmp_path)` directly. The `_make_bare_con()` helper in `test_repo.py` L620–624 uses `:memory:` — appropriate for pure migration tests that don't need a path.

**Warning signs:** `os.path.exists(os.path.expanduser("~/.local/share/musicstreamer/assets/channel-avatars"))` returning True after a test run that shouldn't have touched disk.

[VERIFIED: read from tests/test_repo.py L620–624, tests/test_paths.py L10–17]

### Pitfall 3: `paths.channel_avatars_dir()` Purity Violation

**What goes wrong:** Adding a `os.makedirs(...)` call inside `channel_avatars_dir()` itself instead of only in `ensure_dirs()`.

**Why it happens:** Seems convenient — directory always exists when you call the accessor.

**How to avoid:** `paths.py` is **pure** — importing it or calling any accessor must NOT touch the filesystem (see module docstring L1–15, and `test_paths.py:test_paths_do_no_io_on_import`). Directory creation belongs exclusively in `ensure_dirs()` and in imperative call sites (per `eq_profiles_dir` docstring L94–101: "Pure — does NOT create the directory. Callers use `os.makedirs(...)`").

[VERIFIED: read from musicstreamer/paths.py L1–15, tests/test_paths.py L38–58]

---

## Validation Architecture

`nyquist_validation` is enabled in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (discovered from `tests/conftest.py`, all existing tests use it) |
| Config file | `pyproject.toml` (assumed) or implicit — no `pytest.ini` found |
| Quick run command | `uv run --with pytest pytest tests/test_repo.py -x -q` |
| Full suite command | `uv run --with pytest pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-AVATAR-01 | `channel_avatar_path TEXT` column present after `db_init()`, nullable, no DEFAULT | unit | `pytest tests/test_repo.py::test_channel_avatar_path_migration_idempotent -x` | ❌ Wave 0 |
| ART-AVATAR-01 | Schema convergence: pre-89a schema upgraded = fresh DB (both have identical `PRAGMA table_info`) | unit | `pytest tests/test_repo.py::test_channel_avatar_path_schema_convergence -x` | ❌ Wave 0 |
| ART-AVATAR-02 | `paths.channel_avatars_dir()` returns correct path under `_root_override` | unit | `pytest tests/test_paths.py::test_channel_avatars_dir_honors_root_override -x` | ❌ Wave 0 |
| ART-AVATAR-02 | `paths.channel_avatars_dir()` is pure (does not create directory) | unit | `pytest tests/test_paths.py::test_channel_avatars_dir_does_not_create_directory -x` | ❌ Wave 0 |
| ART-AVATAR-02 | `ensure_dirs()` creates `channel-avatars/` under `_root_override` | unit | `pytest tests/test_repo.py::test_ensure_dirs_creates_channel_avatars_dir -x` (or `test_assets.py`) | ❌ Wave 0 |

### Concrete Test Specifications

#### Test 1 — `test_channel_avatar_path_migration_idempotent` (ART-AVATAR-01, D-07a)

File: `tests/test_repo.py` (append to existing file — matches all existing migration tests)

Fixture: `repo` (L6–13) — calls `db_init()` on a fresh `tmp_path`-based connection.

```python
def test_channel_avatar_path_migration_idempotent(repo):
    """ART-AVATAR-01 D-07: db_init twice must not raise; column has expected schema.

    Mirrors test_cover_art_source_migration_idempotent (test_repo.py L228-252)
    and test_preferred_stream_id_migration_idempotent (test_repo.py L875-897).
    PRAGMA table_info cols: (cid, name, type, notnull, dflt_value, pk).
    channel_avatar_path must be TEXT, nullable (notnull=0), no DEFAULT (None).
    """
    # Second and third db_init calls must not raise.
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "channel_avatar_path" in by_name, (
        f"channel_avatar_path column missing; got {sorted(by_name)}"
    )
    col = by_name["channel_avatar_path"]
    # index 2=type, 3=notnull, 4=dflt_value
    assert col[2] == "TEXT", f"column type must be TEXT; got {col[2]!r}"
    assert col[3] == 0, "channel_avatar_path must be nullable (notnull=0)"
    assert col[4] is None, (
        f"channel_avatar_path must have no DEFAULT; got {col[4]!r}"
    )
```

#### Test 2 — `test_channel_avatar_path_schema_convergence` (ART-AVATAR-01, D-07b)

File: `tests/test_repo.py` (append)

Fixture: `_make_bare_con()` (L620–624) — creates an `:memory:` connection; this helper is the established pattern for pre-migration schema tests (see `test_bitrate_kbps_migration_adds_column` at L642–678 and `test_db_init_idempotent_for_sample_rate_hz` at L780–822).

```python
def test_channel_avatar_path_schema_convergence():
    """ART-AVATAR-01 D-07: fresh DB and upgraded pre-89a DB converge to same schema.

    Builds a pre-89a stations schema (channel_avatar_path absent), runs db_init(),
    and asserts PRAGMA table_info(stations) matches a fresh db_init() DB.
    Mirrors test_bitrate_kbps_migration_adds_column shape (test_repo.py L642-678).
    """
    # --- fresh DB (the target shape) ---
    fresh_con = _make_bare_con()
    db_init(fresh_con)
    fresh_cols = {
        row[1]: (row[2], row[3], row[4])  # (type, notnull, dflt_value)
        for row in fresh_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" in fresh_cols, "fresh DB must have channel_avatar_path"

    # --- pre-89a DB: stations table WITHOUT channel_avatar_path ---
    legacy_con = _make_bare_con()
    legacy_con.executescript("""
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
    """)
    legacy_con.commit()
    # Confirm the column is absent before migration
    pre_cols = {
        row[1] for row in legacy_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" not in pre_cols, "pre-89a fixture must NOT have the column"

    # Apply migration
    db_init(legacy_con)

    # Post-migration schema must match fresh DB
    migrated_cols = {
        row[1]: (row[2], row[3], row[4])
        for row in legacy_con.execute("PRAGMA table_info('stations')").fetchall()
    }
    assert "channel_avatar_path" in migrated_cols, "column absent after migration"
    assert migrated_cols["channel_avatar_path"] == fresh_cols["channel_avatar_path"], (
        f"migrated schema differs from fresh: "
        f"migrated={migrated_cols['channel_avatar_path']!r}, "
        f"fresh={fresh_cols['channel_avatar_path']!r}"
    )

    # Existing row must still exist (data not dropped)
    row = legacy_con.execute("SELECT name, channel_avatar_path FROM stations").fetchone()
    assert row[0] == "ExistingFM"
    assert row[1] is None, "existing row must have NULL channel_avatar_path"
```

#### Test 3 — `test_channel_avatars_dir_honors_root_override` (ART-AVATAR-02)

File: `tests/test_paths.py` (append — mirrors `test_eq_profiles_dir_honors_root_override` at L92–95)

```python
def test_channel_avatars_dir_honors_root_override(monkeypatch, tmp_path):
    """Phase 89A D-02: channel-avatars dir resolves under the override root."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.channel_avatars_dir() == os.path.join(str(tmp_path), "assets", "channel-avatars")

def test_channel_avatars_dir_does_not_create_directory(monkeypatch, tmp_path):
    """Purity contract: helper returns a string; it does NOT mkdir."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    result = paths.channel_avatars_dir()
    assert os.path.exists(result) is False
```

#### Test 4 — `test_ensure_dirs_creates_channel_avatars_dir` (ART-AVATAR-02)

File: `tests/test_repo.py` or a new `tests/test_assets.py` — if `test_assets.py` does not exist, append to `test_repo.py` since `assets.ensure_dirs()` has no dedicated test file currently.

```python
def test_ensure_dirs_creates_channel_avatars_dir(tmp_path, monkeypatch):
    """ART-AVATAR-02 D-01: ensure_dirs() creates channel-avatars/ under _root_override."""
    import musicstreamer.paths as paths_mod
    import musicstreamer.assets as assets_mod
    monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))
    assets_mod.ensure_dirs()
    assert os.path.isdir(os.path.join(str(tmp_path), "assets", "channel-avatars")), (
        "ensure_dirs() must create assets/channel-avatars/"
    )
```

### Sampling Rate

- **Per task commit:** `uv run --with pytest pytest tests/test_repo.py tests/test_paths.py -x -q`
- **Per wave merge:** `uv run --with pytest pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_repo.py` — append `test_channel_avatar_path_migration_idempotent` (REQ ART-AVATAR-01)
- [ ] `tests/test_repo.py` — append `test_channel_avatar_path_schema_convergence` (REQ ART-AVATAR-01, D-07b)
- [ ] `tests/test_paths.py` — append `test_channel_avatars_dir_honors_root_override` + `test_channel_avatars_dir_does_not_create_directory` (REQ ART-AVATAR-02)
- [ ] `tests/test_repo.py` (or `tests/test_assets.py`) — append `test_ensure_dirs_creates_channel_avatars_dir` (REQ ART-AVATAR-02)

---

## Code Examples

All examples verified by reading the actual source files.

### Migration block anchor point — confirmed surrounding context (repo.py L297–311)

```python
# repo.py L297-311 (Phase 83 block — the new block goes immediately after this):
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

[VERIFIED: read from musicstreamer/repo.py L297–311]

### `ensure_dirs()` full current body (assets.py L7–9)

```python
def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
```

[VERIFIED: read from musicstreamer/assets.py L7–9]

### `eq_profiles_dir()` accessor shape to mirror (paths.py L94–101)

```python
def eq_profiles_dir() -> str:
    """Return the directory holding imported AutoEQ profiles (Phase 47.2 D-12).

    Pure — does NOT create the directory. Callers use
    ``os.makedirs(paths.eq_profiles_dir(), exist_ok=True)`` before writing.
    """
    return os.path.join(_root(), "eq-profiles")
```

[VERIFIED: read from musicstreamer/paths.py L94–101]

### PRAGMA table_info assertion style (test_repo.py L875–897, Phase 82 precedent)

```python
# test_repo.py L875-897 — direct template for the new idempotency test:
def test_preferred_stream_id_migration_idempotent(repo):
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name, (...)
    col = by_name["preferred_stream_id"]
    assert col[2] == "INTEGER", ...
    assert col[3] == 0, ...   # nullable
    assert col[4] is None, ...  # no DEFAULT
```

[VERIFIED: read from tests/test_repo.py L875–897]

### `_make_bare_con()` helper (test_repo.py L620–624)

```python
def _make_bare_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
```

[VERIFIED: read from tests/test_repo.py L620–624]

---

## State of the Art

No state-of-the-art changes affect this phase. The additive migration idiom (`try/except OperationalError`) is the project's established pattern across all phases since the initial `url → station_streams` migration. No SQLite `DROP COLUMN` (available since 3.35) is needed or used.

---

## Runtime State Inventory

This phase adds a column and a directory. It does NOT rename, drop, or migrate data values.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | All existing `stations` rows get `channel_avatar_path = NULL` automatically (SQLite default for nullable column) | None — SQLite handles it atomically in ALTER TABLE |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | `musicstreamer.sqlite3` in user's data dir gets new column on first launch post-deploy | Automatic via `db_init()` — user restarts app |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uv run --with pytest pytest` is the correct test invocation for this project | Validation Architecture | Low — adjust run command; tests themselves are valid either way |
| A2 | No dedicated `tests/test_assets.py` exists; `ensure_dirs` tests belong in `test_repo.py` | Validation Architecture | Low — if `test_assets.py` exists, move the one test there |

**All implementation claims (migration idiom, path accessor shape, ensure_dirs body, test fixture style, PRAGMA assertion shape) were verified by reading the actual source files.** Only the test invocation command is assumed.

---

## Open Questions

1. **`test_ensure_dirs_creates_channel_avatars_dir` test file**
   - What we know: no `tests/test_assets.py` exists; `tests/test_repo.py` already imports `os` and uses `tmp_path`.
   - What's unclear: project convention for testing `assets.py` (the module has no test coverage currently).
   - Recommendation: Place in `tests/test_repo.py` with a short comment citing Phase 89A. If a `tests/test_assets.py` is created, it can be moved there.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| sqlite3 (stdlib) | `repo.py:db_init()` | ✓ | Python stdlib | — |
| platformdirs | `paths._root()` | ✓ | Already in requirements | — |
| pytest | Test execution | ✓ | Already in dev requirements | — |

No missing dependencies.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | no | Column is nullable TEXT, no user input in this phase; Phase 89 will validate avatar URLs |
| V6 Cryptography | no | — |

No security concerns in this phase. The new column accepts NULL only; no user-controlled data is written to it until Phase 89. Directory creation with `exist_ok=True` does not change permissions on an existing directory.

---

## Sources

### Primary (HIGH confidence — verified by reading actual source files)

- `musicstreamer/repo.py` L88–311 — `db_init()` full body; additive migration idiom; rebuild block L208–265; Phase 73/82/83 ALTER blocks L267–311
- `musicstreamer/paths.py` L1–101 — `_root_override`, `_root()`, `assets_dir()`, `eq_profiles_dir()`
- `musicstreamer/assets.py` L1–27 — `ensure_dirs()`, `copy_asset_for_station()` relative-path convention
- `tests/test_repo.py` L1–1153 — `repo` fixture L6–13, `_make_bare_con` L620–624, `test_cover_art_source_migration_idempotent` L228–252, `test_preferred_stream_id_migration_idempotent` L875–897, `test_bitrate_kbps_migration_adds_column` L642–678
- `tests/test_paths.py` L1–103 — `_reset_root_override` fixture L10–17, purity test L38–58, `eq_profiles_dir` tests L92–103
- `.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md` — locked decisions D-01 through D-07

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` §ART-AVATAR L75–87 — ART-AVATAR-01, ART-AVATAR-02 requirement text
- `.planning/STATE.md` — phase roster and roadmap context

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all three files read directly; no external packages
- Architecture: HIGH — all four touch points confirmed from source
- Pitfalls: HIGH — Pitfall 1 confirmed by reading the rebuild block and the three correctly-placed Phase 73/82/83 ALTERs after it
- Test patterns: HIGH — fixture style, PRAGMA assertion shape, and `_make_bare_con()` all confirmed from `tests/test_repo.py`

**Research date:** 2026-06-13
**Valid until:** Stable — implementation is a copy of patterns in the same repo; no external dependencies to drift
