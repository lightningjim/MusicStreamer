---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
plan: 01
status: complete
completed_at: 2026-05-22
---

# Phase 83 Plan 01 — SUMMARY

## What landed

Schema + model + repo data foundation for Phase 83 SomaFM prerolls. Pure additive; no existing rows modified. Plans 83-02 (importer) and 83-03 (Player) depend on this.

## Key files

### Schema (D-01, D-04, D-15)
- `musicstreamer/repo.py:153` — `CREATE TABLE IF NOT EXISTS station_prerolls` added inside `db_init`'s `executescript` block (after `station_streams`). Body: `(id INTEGER PK AUTOINCREMENT, station_id INTEGER NOT NULL, url TEXT NOT NULL, position INTEGER NOT NULL, FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE)`.
- `musicstreamer/repo.py:307` — `ALTER TABLE stations ADD COLUMN prerolls_fetched_at INTEGER` wrapped in `try/except sqlite3.OperationalError` for idempotency. Placed AFTER the Phase 82 `preferred_stream_id` ALTER (Pitfall 2 — lands after the `stations_new` rebuild block).
- **`musicstreamer/migration.py` NOT modified** (PATTERNS.md routing invariant — `migration.py` is the platformdirs first-launch helper, not a DDL container).

### Repo methods (D-01, D-03, D-04 + ASVS V5 + DoS cap)
- `musicstreamer/repo.py:406` — `list_prerolls(station_id) -> List[str]`. `SELECT url FROM station_prerolls WHERE station_id = ? ORDER BY position`. Returns `[]` when empty.
- `musicstreamer/repo.py:421` — `insert_preroll(station_id, url, position) -> int`. Validates `url.startswith(("http://", "https://"))` (T-83-01 ASVS V5) and `position <= 50` (T-83-02 DoS cap). Parameterized INSERT (T-83-03 SQLi mitigated by construction).
- `musicstreamer/repo.py:667` — `set_prerolls_fetched_at(station_id, epoch_seconds) -> None`. Single UPDATE; idempotent (last-write-wins).

### Station dataclass (D-01, D-04, Pitfall 6 option 3a)
- `musicstreamer/models.py` — appended two fields after `preferred_stream_id`: `prerolls: List[str] = field(default_factory=list)` and `prerolls_fetched_at: Optional[int] = None`.

### Eager-load on all 4 Station-builder sites (D-01 + Pitfall 6 option 3a)
- `musicstreamer/repo.py:557` — `list_stations`
- `musicstreamer/repo.py:596` — `get_station`
- `musicstreamer/repo.py:705` — `list_recently_played`
- `musicstreamer/repo.py:820` — `list_favorite_stations`

Each adds `prerolls=self.list_prerolls(<row_id>)` and `prerolls_fetched_at=r["prerolls_fetched_at"]`. No JOIN; one extra sub-query per station (RESEARCH Assumption A8 — ~1ms for a 200-station library).

### Tests (D-01, D-04, D-14, D-15)
- `tests/test_repo.py` — appended 10 tests:
  1. `test_station_prerolls_table_schema_after_db_init` — PRAGMA schema + FK CASCADE
  2. `test_prerolls_fetched_at_column_after_db_init` — PRAGMA INTEGER nullable no-default
  3. `test_db_init_is_idempotent_for_phase_83_additions` — second `db_init` no-op
  4. `test_insert_preroll_and_list_prerolls_round_trip` — CRUD
  5. `test_list_prerolls_orders_by_position_not_insert_order` — ORDER BY load-bearing
  6. `test_insert_preroll_rejects_non_http_scheme` — T-83-01 ASVS V5
  7. `test_insert_preroll_rejects_position_over_cap` — T-83-02 DoS
  8. `test_set_prerolls_fetched_at_round_trips_via_all_4_station_builders` — Phase 82 setter-round-trip shape
  9. `test_eager_load_prerolls_via_all_4_station_builders` — Pitfall 6 detection
  10. `test_delete_station_cascades_station_prerolls` — FK CASCADE invariant

No new fixtures; reused `_seed_two_stream_station` from Phase 82.

## Verification

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_repo.py -k "station_prerolls or prerolls_fetched_at or insert_preroll or list_prerolls or set_prerolls_fetched_at or eager_load_prerolls or delete_station_cascades_station_prerolls or db_init_is_idempotent_for_phase_83" -q` | 10 passed |
| `uv run pytest tests/test_repo.py -q` | 88 passed (78 existing + 10 new) |
| `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q` | 128 passed |
| `grep -c 'CREATE TABLE IF NOT EXISTS station_prerolls' musicstreamer/repo.py` | 1 |
| `grep -c 'ADD COLUMN prerolls_fetched_at INTEGER' musicstreamer/repo.py` | 1 |
| `grep -c 'prerolls: List\[str\]' musicstreamer/models.py` | 1 |
| `grep -c 'prerolls=self.list_prerolls' musicstreamer/repo.py` | 4 |
| `grep -c 'def insert_preroll\|def list_prerolls\|def set_prerolls_fetched_at' musicstreamer/repo.py` | 3 |

## Key decisions (carryover for downstream plans)

- **List[str] not Preroll dataclass** — Player only consumes URLs; no need for a dataclass (RESEARCH Operation 2).
- **No JOIN aggregate** — extra sub-query per row is fine (~1ms for 200 stations).
- **URL-scheme validation + DoS cap at Repo boundary** — defense in depth alongside `soma_import._safe_urlopen_request`. The next gate is in 83-02 (importer per-channel cap of 50 with `_log.warning`).

## Self-Check: PASSED

All `<done>` blocks satisfied; full suite green (128/128); no regressions.

## Created Files
None — all edits are appends to existing files.

## Key Files Modified
- `musicstreamer/repo.py` — schema, 3 new methods, 4 builder eager-loads (~80 lines added)
- `musicstreamer/models.py` — 2 new Station fields (~2 lines added)
- `tests/test_repo.py` — 10 new tests (~160 lines added)

## Followups for 83-02 / 83-03
- 83-02: `repo.insert_preroll` is ready; loop SomaFM `preroll[]` array inside the existing per-channel try block BEFORE `inserted_station_id = None` (Pitfall 4).
- 83-02: `repo.set_prerolls_fetched_at` is ready; call once per imported channel with `int(time.time())` even when `preroll[]` is empty (D-04 marker semantics).
- 83-03: `Station.prerolls` is eager-loaded everywhere; `random.choice(station.prerolls)` in `Player.play` will work directly.
- 83-03: `Station.prerolls_fetched_at` distinguishes "never fetched" (NULL) from "fetched, 0 prerolls" (non-NULL int).
