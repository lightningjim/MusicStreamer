# Phase 89a: Channel-Avatar DB Migration + Storage Layout - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Foundation only: add an additive `channel_avatar_path TEXT` column to the `stations` table (idempotent, rollback-safe) and establish the on-disk avatar storage directory `~/.local/share/musicstreamer/assets/channel-avatars/`. **Zero behavior change** — no avatar fetching, no cover-slot swap, no UI. Those are Phases 89 (YouTube fetch + cover-slot) and 89b (Twitch fetch).

Delivers requirements ART-AVATAR-01 and ART-AVATAR-02.

</domain>

<decisions>
## Implementation Decisions

### Directory creation timing *(discussed)*
- **D-01:** The `assets/channel-avatars/` directory is created **eagerly** in `musicstreamer/assets.py:ensure_dirs()` via `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`. `ensure_dirs()` runs at startup, so the directory always exists — this directly satisfies Success Criterion 3 ("directory exists with appropriate permissions") and makes the phase verifiable from real disk state without needing to write an avatar.
- **D-02:** Expose the path via a **dedicated `paths.channel_avatars_dir()` helper** returning `os.path.join(_root(), "assets", "channel-avatars")`, mirroring the existing `paths.assets_dir()` accessor. It must respect `_root_override` (the existing monkeypatch convention) so tests redirect it like every other path. Both `ensure_dirs()` and the future Phase 89 avatar writer call this helper — no duplicated path strings.

### Storage layout *(locked from requirements — not discussed)*
- **D-03:** **Flat layout** — avatars stored as `assets/channel-avatars/<station-id>.png`, one PNG per station keyed by station ID, per **ART-AVATAR-02**. This resolves the tension with Success Criterion 3's wording ("layout matching the existing `assets/` station-logo precedent") — the precedent in `assets.py:copy_asset_for_station` is actually a per-station *subdirectory* layout (`assets/<id>/station_art.png`), but the explicit requirement text (ART-AVATAR-02) wins: a single flat `channel-avatars/` directory, not per-station subdirs. The column will store a path **relative to `data_dir()`** (e.g. `assets/channel-avatars/12.png`), mirroring how `station_art_path` stores `assets/12/station_art.png`.

### Migration mechanics *(locked from precedent — not discussed)*
- **D-04:** Add the column using the established idempotent idiom in `repo.py:db_init()`:
  ```python
  try:
      con.execute("ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT")
      con.commit()
  except sqlite3.OperationalError:
      pass  # column already exists — idempotent
  ```
  Nullable `TEXT`, no `DEFAULT` (NULL = no avatar stored). Existing rows get NULL automatically.
- **D-05:** The `ALTER TABLE` MUST land **after** the legacy `stations_new` rebuild block (`repo.py` ~L208–265), for the same **Pitfall 2** reason documented in the Phase 73/82/83 column additions: the rebuild's `CREATE TABLE stations_new` / `INSERT … SELECT` does not carry dynamically-added columns, so placing the ALTER after the rebuild ensures the column lands on the rebuilt (or fresh) table. Follow the existing inline-comment convention citing the pitfall.

### Column plumbing scope *(locked — not discussed)*
- **D-06:** Phase 89a is **migration + directory ONLY**. The column exists in the DB and sits NULL for every row. Do **not** thread `channel_avatar_path` through the `Station` dataclass (`models.py`), the row→`Station` mappers, or `save_station()` in this phase — that wiring is deferred to **Phase 89**, when there's actually a value to read/write. This keeps the "zero behavior change" guarantee literal and the phase minimal.

### Rollback / idempotency test scope *(locked — not discussed)*
- **D-07:** The migration test must prove **idempotency** (run `db_init()` twice on the same connection → no raise, schema unchanged) and the **rollback semantics** of Success Criterion 2. Because SQLite has no `DROP COLUMN` before 3.35 (and the project's additive pattern never drops), "revert + re-apply produces identical schema" is interpreted as: starting from a pre-89a schema (column absent), applying the migration yields the `channel_avatar_path` column; a fresh DB created via the full `db_init()` and an upgraded DB converge to the **same** `PRAGMA table_info(stations)` output. The planner/researcher should define the concrete revert mechanism (e.g. a test fixture that builds the prior schema, or asserting `table_info` equality between fresh-create and upgrade paths) — the *intent* is schema convergence + double-run safety, not a literal column drop.

### Claude's Discretion
- Exact test file location and fixture style (follow existing `repo.py` migration tests).
- Whether `ensure_dirs()` gets one combined makedirs block or a separate line — match surrounding style.
- Inline comment wording for the new ALTER (mirror Phase 82/83 comments).

</decisions>

<specifics>
## Specific Ideas

- Mirror the existing patterns exactly: this phase is a "direct mirror of existing `station_art_path` / `album_fallback_path` migration pattern" (ROADMAP Research flag note). Consistency with `repo.py`'s try/except-`OperationalError` idiom and `paths.py`'s `_root()`-based accessors is the goal, not novelty.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §ART-AVATAR (lines ~75–86) — ART-AVATAR-01 (column via idempotent additive migration matching `station_art_path`) and ART-AVATAR-02 (flat `assets/channel-avatars/` directory keyed by station ID) are the locked requirements for this phase. ART-AVATAR-03..10 are downstream (Phases 89/89b) context.

### Roadmap
- `.planning/ROADMAP.md` §"Phase 89a" (lines ~178–190) — Goal, Depends-on (nothing in v2.2; parallel-eligible), and the three Success Criteria (column present + NULL default + existing data unchanged; idempotent double-run + rollback test; directory exists with appropriate permissions).

### Code precedent (read before implementing)
- `musicstreamer/repo.py` §`db_init()` (lines ~88–311) — the additive-migration idiom and the Pitfall-2 ordering constraint (ALTER must follow the `stations_new` rebuild block). The Phase 73 `cover_art_source`, Phase 82 `preferred_stream_id`, and Phase 83 `prerolls_fetched_at` additions (L267–311) are the closest analogs to copy.
- `musicstreamer/assets.py` — `ensure_dirs()` (where the eager makedirs goes) and `copy_asset_for_station()` (the relative-path-under-`assets/` convention to mirror for the column value).
- `musicstreamer/paths.py` — `_root()` / `_root_override` test convention and `assets_dir()` (the accessor `channel_avatars_dir()` mirrors).
- `musicstreamer/models.py` §`Station` dataclass (`station_art_path: Optional[str]`) — **reference only**; deliberately NOT modified in this phase (see D-06).

No external specs/ADRs beyond the above — requirements are fully captured here and in REQUIREMENTS.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `repo.py:db_init()` additive-migration idiom (try `ALTER TABLE … ADD COLUMN` / except `sqlite3.OperationalError: pass`) — copy verbatim for the new column.
- `assets.py:ensure_dirs()` — append the new `os.makedirs(...)` line here for eager directory creation.
- `paths.py:assets_dir()` — template for the new `channel_avatars_dir()` accessor; `_root_override` gives free test isolation.
- `assets.py:copy_asset_for_station()` — establishes the "store path relative to `data_dir()`" convention the column value follows (Phase 89 will use this shape).

### Established Patterns
- **Pitfall 2 ordering:** every dynamically-added `stations` column must `ALTER` *after* the `stations_new` rebuild block (~repo.py L208–265), or the rebuild silently drops it. Documented inline in the Phase 73/82/83 additions.
- **Idempotency via `OperationalError` catch:** re-running `db_init()` is safe because each ALTER swallows "duplicate column" errors.
- **Path accessors are monkeypatch-friendly:** tests set `paths._root_override`; never hardcode absolute paths.

### Integration Points
- `repo.py:db_init()` — new ALTER block (after the rebuild, alongside Phase 73/82/83 ALTERs).
- `assets.py:ensure_dirs()` — new eager makedirs call.
- `paths.py` — new `channel_avatars_dir()` accessor.
- (Deferred to Phase 89, NOT this phase: `models.py` `Station` dataclass, row mappers, `save_station()`.)

</code_context>

<deferred>
## Deferred Ideas

- Threading `channel_avatar_path` through the `Station` dataclass, row→Station mappers, and `save_station()` — **Phase 89** (when there's a value to persist).
- `yt_import.fetch_channel_avatar()` and the YouTube cover-slot swap — **Phase 89** (ART-AVATAR-03, 05–10).
- Twitch Helix `profile_image_url` fetch — **Phase 89b** (ART-AVATAR-04).

</deferred>

---

*Phase: 89A-channel-avatar-db-migration-storage-layout*
*Context gathered: 2026-06-07*
