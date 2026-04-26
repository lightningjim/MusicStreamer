# Phase 47: Stream bitrate quality ordering — Research

**Researched:** 2026-04-17
**Domain:** Python 3 / SQLite / PySide6 (QTableWidget, QLineEdit+QIntValidator) / dataclass schema evolution
**Confidence:** HIGH (all call sites verified in-tree; no external lib lookups needed)

## Summary

All technical questions resolved by reading the tree. The existing codebase has exactly the idioms the plan needs: additive `ALTER TABLE` migrations wrapped in `try/except sqlite3.OperationalError`, a pure stream-list iteration site in `player.py::play`, a centralized `_station_to_dict` serializer in `settings_export.py`, and a straightforward 4-column `QTableWidget` in `edit_station_dialog.py`. One notable gap was uncovered: there is **no** `musicstreamer/radio_browser_import.py` module — RadioBrowser save-to-library happens directly inside `DiscoveryDialog._on_save_row` and flows through `repo.insert_station()`, which today persists neither codec nor bitrate. Plan must extend that save path.

**Primary recommendation:** Follow the existing additive-ALTER idiom in `repo.py`, widen `insert_stream`/`update_stream`/`list_streams` to accept and hydrate `bitrate_kbps`, add `bitrate_kbps` to the explicit `_station_to_dict` serializer with a `.get("bitrate_kbps", 0)` defensive default on the import side, extend `DiscoveryDialog._on_save_row` to write an explicit stream with bitrate (bypassing `insert_station`'s auto-stream path, or widening `insert_station` to accept stream metadata — recommend the former: call `insert_station` then `update_stream` to fix up the auto-created stream, mirroring the pattern already used by `aa_import.import_stations_multi`).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Model / Schema**
- **D-01:** Add `bitrate_kbps: int = 0` to `StationStream` dataclass in `musicstreamer/models.py`. Default 0 means "unknown".
- **D-02:** DB migration follows the existing additive pattern in `musicstreamer/repo.py` — a `try: con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0"); except sqlite3.OperationalError: pass` block alongside the other column migrations. No PRAGMA `user_version` bump; the additive pattern is idempotent.
- **D-03:** Keep the existing `quality: str` field. `quality` remains a human-facing label ("hi" / "med" / "low" / custom tags); `bitrate_kbps` is the new numeric sort key. Failover uses `bitrate_kbps`; UI shows quality label alongside bitrate. Preserves user custom tags; no migration of existing `quality` values.

**Failover Ordering Algorithm**
- **D-04:** Sort streams within a station by `(codec_rank desc, bitrate_kbps desc, position asc)`.
- **D-05:** Codec ranks: `FLAC=3 > AAC=2 > MP3=1 > other=0`. Unknown/empty codec → rank 0.
- **D-06:** Cross-codec tie at same bitrate: AAC ranks above MP3 (efficiency advantage). Covered by codec_rank.
- **D-07:** **Unknown bitrates (`bitrate_kbps == 0`) sort LAST.** Known-bitrate streams come first ordered by `(codec_rank desc, bitrate_kbps desc)`; unknowns fall to the bottom and keep their relative `position asc` order among themselves.
- **D-08:** `codec_rank` and `order_streams` live in a **new** module `musicstreamer/stream_ordering.py`. Kept out of `models.py` to avoid widening the dataclass file.
- **D-09:** The function is **pure** — takes a `list[StationStream]`, returns a new sorted list. No DB access, no mutation of the input.

**AA Import**
- **D-10:** `aa_import.py` populates `bitrate_kbps` from DI.fm quality tiers: `hi=320`, `med=128`, `low=64`. Codec remains `"AAC"` for DI.fm. `quality` field stays set to the tier string.

**RadioBrowser Import**
- **D-11:** RadioBrowser API returns `bitrate: int` per stream. Populate `bitrate_kbps` directly. If absent or 0, leave `bitrate_kbps=0` (unknown).

**Edit Station Dialog**
- **D-12:** Add a 5th column to `streams_table` in `edit_station_dialog.py`. Layout: **URL | Quality | Codec | Bitrate | Position**. Bitrate is a `QLineEdit` with `QIntValidator(0, 9999, parent)`. `0` renders as empty string in the cell for readability (stores as 0).
- **D-13:** `QTableWidget` cell editor uses the default delegate with `QLineEdit` + validator. No combo box, no spinner.
- **D-14:** Save path: read bitrate cell as `int(text or "0")`.

### Claude's Discretion

- Exact file path for `stream_ordering.py` — lean toward top-level `musicstreamer/stream_ordering.py` to mirror `aa_import.py`, `settings_export.py`.
- Test file name: `tests/test_stream_ordering.py`, table-driven unit tests mirroring `tests/test_aa_import.py` style.
- Whether to add an inline "computed order" preview column to Edit dialog — lean **no** (keep UI simple).
- AA tier map location — inline constant near existing quality-tier code in `aa_import.py`.

### Deferred Ideas (OUT OF SCOPE)

- SEED-005 stats-for-nerds buffer indicator → **Phase 47.1**
- SEED-007 AutoEQ parametric EQ import → **Phase 47.2**
- Per-stream live bitrate measurement (ICY metadata) — future phase
- Auto-detect bitrate on stream add (probe URL on import) — future phase
- Per-user "prefer lower bitrate for mobile data" toggle — future phase
- `quality` field cleanup / deprecation — revisit later
</user_constraints>

## Project Constraints (from CLAUDE.md)

- `~/.claude/CLAUDE.md` developer profile: terse-direct communication, fast-intuitive decisions, concise explanations, pragmatic UX. Plans should not produce menu-of-options trees or over-engineered frameworks for what is a tight additive field.
- `./CLAUDE.md` (project-level) is the user's personal memory note — no project-specific coding directives for MusicStreamer apply here.
- No `.claude/skills/` or `.agents/skills/` directories present in the repo — no per-project skill rules to honor.

## Existing Patterns

### 1. Additive ALTER TABLE migration (exact idiom)

In `musicstreamer/repo.py`, `db_init` already contains three instances of this exact shape (lines 66–82):

```python
try:
    con.execute("ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

The Phase 47 migration reuses this shape verbatim, targeting `station_streams`:

```python
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

**Confirmed table name:** `station_streams` (from `repo.py:51`; CREATE TABLE IF NOT EXISTS declares it; all queries in repo use that spelling). CONTEXT's uncertain spellings `streams` and `station_stream` are not used.

The inline CREATE TABLE at the top of `db_init` must also gain the new column so fresh installs land on the final schema directly:

```sql
CREATE TABLE IF NOT EXISTS station_streams (
    ...
    codec TEXT NOT NULL DEFAULT '',
    bitrate_kbps INTEGER NOT NULL DEFAULT 0,  -- NEW
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
);
```

### 2. `StationStream` construction / iteration sites

Production code uses keyword args; adding a `bitrate_kbps: int = 0` default is backward-compatible at every site. Verified construction sites in `musicstreamer/`:

| File | Line | Usage |
|------|------|-------|
| `musicstreamer/repo.py` | 173 | Hydration — must pass `bitrate_kbps=r["bitrate_kbps"]` |
| `musicstreamer/__main__.py` | 47 | Smoke-test stream — no change required (default 0) |
| `musicstreamer/ui_qt/discovery_dialog.py` | 468 | Preview-only temp stream for Radio-Browser — no change required (default 0) |

Test-only construction sites (7 files) all pass keyword args and are auto-compatible with the new default.

### 3. `_station_to_dict` — explicit, not `asdict`

`musicstreamer/settings_export.py:101-122` hand-rolls the dict (no `dataclasses.asdict`). Grep for `asdict` in the tree: zero hits. This is good — no hidden serialization path will silently pick up the new field. Every surface that needs to emit or read `bitrate_kbps` must be edited explicitly. See Gotcha 1.

### 4. Edit Station `QTableWidget` 4-column idiom

`edit_station_dialog.py:275-287` defines a `QTableWidget(0, 4)` with column constants `_COL_URL/_COL_QUALITY/_COL_CODEC/_COL_POSITION` (lines 147–150). The header row, resize modes, widths, and population (`_add_stream_row`, line 399) all key off these constants. Extending to 5 columns is:

1. Add `_COL_BITRATE = 3` and bump `_COL_POSITION = 4` (these are currently 2 and 3).
2. `QTableWidget(0, 4)` → `QTableWidget(0, 5)` at line 275.
3. `setHorizontalHeaderLabels([..., "Bitrate", ...])` — insert "Bitrate" between "Codec" and "Position".
4. Add `hdr.setSectionResizeMode(_COL_BITRATE, QHeaderView.Fixed)` and `setColumnWidth(_COL_BITRATE, 70)`.
5. Extend `_add_stream_row` signature with `bitrate_kbps: int = 0` and `setItem(row, _COL_BITRATE, QTableWidgetItem(str(bitrate_kbps) if bitrate_kbps else ""))`.
6. Update `_populate` (line 354) to pass `s.bitrate_kbps` to `_add_stream_row`.
7. `_swap_rows` (line 442) already iterates `range(table.columnCount())` — works for 5 columns unchanged.
8. `_on_save` loop (line 667) reads each column; add a bitrate read with `int(text or "0")` coercion.

**QIntValidator placement:** `QTableWidget`'s default item delegate edits cells with a `QLineEdit`, but attaching a `QIntValidator` to that in-cell editor requires either a custom `QStyledItemDelegate` that installs the validator in `createEditor`, or a no-delegate approach where the cell stores a plain `QTableWidgetItem` (str) and the save path does defensive `int(text or "0")` coercion. Given D-14 ("read the bitrate column as `int(text or \"0\")`") and D-13 ("default delegate with `QLineEdit` + validator, no combo box, no spinner"), **the simplest implementation is a minimal `QStyledItemDelegate` subclass that returns `QLineEdit(parent); editor.setValidator(QIntValidator(0, 9999, parent))`** — applied to the single column via `streams_table.setItemDelegateForColumn(_COL_BITRATE, BitrateDelegate())`. This honors D-13 literally and keeps the save-path coercion (D-14) as the authoritative parse step even if a user bypasses the validator (e.g. by pasting).

## Technical Gotchas

### G-1: Serialization surfaces and backwards-compat on import

`settings_export.py` is the ONLY serialization boundary for `StationStream`. Two functions touch it:

- **`_station_to_dict` (export, line 101)** — hand-rolled dict literal. Add one key: `"bitrate_kbps": s.bitrate_kbps`. Without this edit, exports will **silently drop** the field (the new dataclass default 0 means this does not raise, but the ZIP round-trip will reset the value — regression).
- **`_insert_station` (commit, line 371) and `_replace_station` (commit, line 426)** — both execute raw SQL `INSERT INTO station_streams ... VALUES (?,?,?,?,?,?,?)` with 7 fields. Must extend to 8 fields and add `stream.get("bitrate_kbps", 0)` to both tuples. The defensive `.get(..., 0)` default **is the forward-compat mechanism** for importing pre-47 ZIPs: older archives won't have the key, and `.get` returns 0, which is the "unknown" sentinel per D-01.

No separate schema-validator exists in `settings_export.py` — `preview_import` only validates version number and archive safety, not per-station schema. `.get("bitrate_kbps", 0)` is sufficient; no additional guard needed.

### G-2: RadioBrowser save path does not go through a dedicated module

**CONTEXT assumption contradicted.** The CONTEXT references `musicstreamer/radio_browser_import.py` (with "(or wherever RadioBrowser imports live — confirm during research)"). That module does **not** exist. RadioBrowser has two surfaces:

- `musicstreamer/radio_browser.py` — HTTP client (search_stations / fetch_tags / fetch_countries). No import logic.
- `musicstreamer/ui_qt/discovery_dialog.py::_on_save_row` (lines 414–430) — the actual save-to-library path. Calls `self._repo.insert_station(name, url, provider_name, tags)`.

`Repo.insert_station` (repo.py:397-407) creates a station and, if `url` is non-empty, calls `self.insert_stream(station_id, url)` — with no codec, no quality, no bitrate. **RadioBrowser bitrate is therefore not persisted today**, even though `DiscoveryDialog` already shows it in the UI (discovery_dialog.py:349).

**Plan must choose one of:**

1. **(Recommended)** Follow the `aa_import.import_stations_multi` pattern: in `_on_save_row`, after calling `insert_station` get the auto-created stream via `list_streams(station_id)[0]`, then `update_stream(stream.id, url, "", "", position=1, stream_type="", codec="", bitrate_kbps=bitrate_val)`. Minimal API surface change — only widens `insert_stream`/`update_stream`/`list_streams` signatures (which already have to widen anyway for AA + settings roundtrip).
2. Widen `Repo.insert_station` to accept optional `bitrate_kbps=0` (and maybe `codec` too). Broader surface change; touches more call sites.

Recommend Option 1. It matches the existing AA pattern and keeps `insert_station`'s signature stable.

### G-3: `Repo.insert_stream` / `update_stream` / `list_streams` — widen signatures

Three repo methods must accept and persist `bitrate_kbps`:

- `list_streams` (line 169) — add `bitrate_kbps=r["bitrate_kbps"]` to the `StationStream(...)` construction. Post-migration, every row has the column with default 0, so `r["bitrate_kbps"]` is safe.
- `insert_stream` (line 177) — add `bitrate_kbps: int = 0` param, append to the VALUES tuple and column list.
- `update_stream` (line 186) — add `bitrate_kbps: int = 0` param, append to the SET clause and tuple.

Existing callers that don't pass `bitrate_kbps` remain correct (default 0 = unknown). Callers that should pass it:
- `aa_import.import_stations_multi` (line 192, 198) — pass `bitrate_kbps=320/128/64` per tier.
- `edit_station_dialog._on_save` (line 685, 688) — pass the parsed int.
- `settings_export._insert_station` + `_replace_station` — raw SQL, not repo methods. Widen the SQL directly (see G-1).

### G-4: Failover algorithm — all-unknowns degenerate to position order

Per D-07, if every stream has `bitrate_kbps == 0`, all fall into the "unknowns bucket" and sort by `position asc`. That is exactly the current v1.5 behavior (`player.py:166` already does `sorted(station.streams, key=lambda s: s.position)`). Safe degeneration, no regression.

### G-5: QIntValidator + empty cell round-trip

`QIntValidator(0, 9999, parent)` rejects non-numeric input but allows the empty string as an "intermediate" state (Qt convention for partial typing). D-14 mandates `int(text or "0")`, so empty cells parse as 0, matching display-as-empty (D-12: `"0 renders as empty string"`). Full round-trip:

- Display: `bitrate_kbps = 0` → cell text `""`
- User types/edits: validator enforces integer characters only
- Save: `int(text or "0") = 0` → stored as 0

Avoid `int(text)` unguarded — an empty cell raises `ValueError`. D-14 already addresses this; the plan task MUST spell out the `or "0"` fallback.

### G-6: `order_streams` must not mutate its input

D-09: pure function. Callers may hold the original list elsewhere (e.g., `Station.streams` — a dataclass field). Use `sorted(streams, key=...)` (returns new list), never `streams.sort(...)` (mutates in place).

### G-7: Player `play()` queue construction — failover hook point

The failover queue is built at `player.py:166-180`:

```python
# Build ordered stream queue: preferred quality first, then rest in position order
streams_by_position = sorted(station.streams, key=lambda s: s.position)
preferred = None
if preferred_quality:
    preferred = next(
        (s for s in streams_by_position if s.quality == preferred_quality), None,
    )
if preferred:
    queue = [preferred] + [s for s in streams_by_position if s is not preferred]
else:
    queue = list(streams_by_position)
self._streams_queue = queue
```

The minimal plug-in for Phase 47: replace `sorted(station.streams, key=lambda s: s.position)` with `order_streams(station.streams)`. Everything else (preferred-quality short-circuit, the `[preferred] + rest` slice) continues to work because `order_streams` returns a list that respects position order for ties — preferred-quality overlay remains intact.

**Note:** `play_stream` (line 182) bypasses the queue for single-stream manual play — no change needed. `_try_next_stream` (line 296) just pops — no change needed.

## Call-Site Map

Verified file:line locations for the planner:

| Surface | File | Line | Edit |
|---------|------|------|------|
| `StationStream` dataclass | `musicstreamer/models.py` | 12-20 | Add `bitrate_kbps: int = 0` between `codec` and class end |
| CREATE TABLE inline | `musicstreamer/repo.py` | 51-61 | Add `bitrate_kbps INTEGER NOT NULL DEFAULT 0` line |
| ALTER TABLE migration | `musicstreamer/repo.py` | after line 82 | New try/except block (see pattern above) |
| `list_streams` hydration | `musicstreamer/repo.py` | 169-175 | Add `bitrate_kbps=r["bitrate_kbps"]` to StationStream() |
| `insert_stream` | `musicstreamer/repo.py` | 177-184 | Add param + SQL column/value |
| `update_stream` | `musicstreamer/repo.py` | 186-191 | Add param + SQL SET clause |
| AA tier → bitrate map | `musicstreamer/aa_import.py` | ~136 (near position_map) | Add `bitrate_map = {"hi": 320, "med": 128, "low": 64}` |
| AA stream dict build | `musicstreamer/aa_import.py` | 149-154 | Add `"bitrate_kbps": bitrate_map[quality]` |
| AA import apply | `musicstreamer/aa_import.py` | 192-202 | Pass `bitrate_kbps=s.get("bitrate_kbps", 0)` to update_stream/insert_stream |
| RadioBrowser save | `musicstreamer/ui_qt/discovery_dialog.py` | 414-430 | After `insert_station`, fix up auto-created stream with bitrate_kbps via `list_streams(..)[0]` + `update_stream` |
| Failover queue build | `musicstreamer/player.py` | 166 | Replace `sorted(station.streams, key=lambda s: s.position)` with `order_streams(station.streams)` |
| Stream table columns | `musicstreamer/ui_qt/edit_station_dialog.py` | 147-150 | Add `_COL_BITRATE = 3`; bump `_COL_POSITION = 4` |
| Stream table ctor | `musicstreamer/ui_qt/edit_station_dialog.py` | 275-287 | `QTableWidget(0, 5)`; insert "Bitrate" header; widths |
| Stream row populate | `musicstreamer/ui_qt/edit_station_dialog.py` | 354-355 (call) + 399-416 (def) | Thread `bitrate_kbps` through `_add_stream_row` |
| Stream row save | `musicstreamer/ui_qt/edit_station_dialog.py` | 667-696 | Read + parse bitrate cell; pass to `update_stream`/`insert_stream` |
| Export serializer | `musicstreamer/settings_export.py` | 101-122 | Add `"bitrate_kbps": s.bitrate_kbps` to stream dict |
| Import insert SQL | `musicstreamer/settings_export.py` | 371-386 | Add 8th column + `stream.get("bitrate_kbps", 0)` |
| Import replace SQL | `musicstreamer/settings_export.py` | 426-440 | Same: add 8th column + defensive `.get` |
| NEW module | `musicstreamer/stream_ordering.py` | new file | `codec_rank(codec)` + `order_streams(streams)` |
| NEW test | `tests/test_stream_ordering.py` | new file | Table-driven pure-function tests |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest>=9` + `pytest-qt>=4` (per `pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_stream_ordering.py -x` |
| Full suite command | `pytest` |

Qt tests run via `pytest-qt` with the offscreen platform (QA-01 precedent set in Phase 36). The `qtbot` fixture is already used throughout `tests/test_edit_station_dialog.py`.

### Requirements → Test Map

Phase has no formal `phase_req_ids` (null per CONTEXT). Using CONTEXT `## Phase Boundary` must-haves as implicit requirements:

| Must-have | Behavior | Test Type | Automated Command | File |
|-----------|----------|-----------|-------------------|------|
| PB-01 (add field) | `StationStream(bitrate_kbps=0)` default; round-trips through repo | unit | `pytest tests/test_repo.py -x -k bitrate` | ❌ Wave 0 new test |
| PB-02 (migration) | Pre-47 DB missing column; `db_init` adds it with default 0 | unit | `pytest tests/test_repo.py -x -k migration` | ❌ Wave 0 new test |
| PB-03 (order_streams — all-known, same codec) | 320 > 128 > 64 | unit | `pytest tests/test_stream_ordering.py::test_same_codec_bitrate_sort -x` | ❌ Wave 0 new file |
| PB-04 (order_streams — cross-codec) | FLAC > AAC > MP3 regardless of bitrate (per codec_rank) | unit | `pytest tests/test_stream_ordering.py::test_codec_rank_wins -x` | ❌ Wave 0 new file |
| PB-05 (order_streams — same codec, same bitrate) | `position asc` tiebreak | unit | `pytest tests/test_stream_ordering.py::test_position_tiebreak -x` | ❌ Wave 0 new file |
| PB-06 (order_streams — cross-codec same bitrate) | AAC > MP3 at 128kbps | unit | `pytest tests/test_stream_ordering.py::test_aac_beats_mp3 -x` | ❌ Wave 0 new file |
| PB-07 (order_streams — all-unknown) | Degenerates to position order | unit | `pytest tests/test_stream_ordering.py::test_all_unknown_position_order -x` | ❌ Wave 0 new file |
| PB-08 (order_streams — mixed known+unknown) | Knowns first (sorted), unknowns last (by position) | unit | `pytest tests/test_stream_ordering.py::test_mixed_known_unknown -x` | ❌ Wave 0 new file |
| PB-09 (order_streams — empty) | `order_streams([])` returns `[]` | unit | `pytest tests/test_stream_ordering.py::test_empty_list -x` | ❌ Wave 0 new file |
| PB-10 (codec_rank) | FLAC=3, AAC=2, MP3=1, unknown=0, case-insensitive, whitespace-tolerant | unit | `pytest tests/test_stream_ordering.py::test_codec_rank -x` | ❌ Wave 0 new file |
| PB-11 (order_streams purity) | Input list not mutated; new list returned | unit | `pytest tests/test_stream_ordering.py::test_does_not_mutate_input -x` | ❌ Wave 0 new file |
| PB-12 (AA import — hi/med/low mapping) | Mocked DI.fm response → StationStream.bitrate_kbps=320/128/64 | integration | `pytest tests/test_aa_import.py -x -k bitrate` | ❌ Wave 0 extend existing file |
| PB-13 (RadioBrowser save path) | `_on_save_row` with bitrate=128 in row → persisted stream has bitrate_kbps=128 | integration | `pytest tests/test_discovery_dialog.py -x -k bitrate` | ❌ Wave 0 extend existing file |
| PB-14 (settings export roundtrip) | build_zip → preview_import → commit_import preserves bitrate_kbps | integration | `pytest tests/test_settings_export.py -x -k bitrate` | ❌ Wave 0 extend existing file |
| PB-15 (settings import forward-compat) | Pre-47 ZIP (no bitrate_kbps key) imports cleanly with 0 default | integration | `pytest tests/test_settings_export.py -x -k forward_compat` | ❌ Wave 0 extend existing file |
| PB-16 (EditStationDialog 5th column) | Dialog populates Bitrate column from StationStream; save writes parsed int | widget | `pytest tests/test_edit_station_dialog.py -x -k bitrate` | ❌ Wave 0 extend existing file |
| PB-17 (EditStationDialog empty cell) | Empty bitrate cell saves as 0 (no ValueError) | widget | `pytest tests/test_edit_station_dialog.py -x -k empty_bitrate` | ❌ Wave 0 extend existing file |
| PB-18 (player integration) | `Player.play(station)` with mixed-bitrate streams builds queue in order_streams order | integration | `pytest tests/test_player_failover.py -x -k bitrate` | ❌ Wave 0 extend existing file |
| PB-19 (grep regression guard) | `grep -c "bitrate_kbps" musicstreamer/` returns non-zero for all expected files | smoke | Inline bash check in plan verify step | n/a |

### Sampling Rate

- **Per task commit:** `pytest tests/test_stream_ordering.py tests/test_repo.py -x` (fastest — pure + DB, ~2-3s)
- **Per wave merge:** `pytest tests/test_stream_ordering.py tests/test_repo.py tests/test_aa_import.py tests/test_settings_export.py tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_player_failover.py -x`
- **Phase gate:** `pytest` (full suite green before `/gsd-verify-work`)

### Wave 0 Gaps

- `tests/test_stream_ordering.py` — new file; covers PB-03 through PB-11
- Extend `tests/test_aa_import.py` — add bitrate-tier assertions (PB-12) alongside existing `test_quality_tier_mapping`
- Extend `tests/test_settings_export.py` — add round-trip + forward-compat cases (PB-14, PB-15); the existing `test_commit_merge_add` already shows the payload schema style
- Extend `tests/test_edit_station_dialog.py` — add 5-column + empty-cell save cases (PB-16, PB-17); pattern mirrors existing `test_name_field_populated` + MagicMock repo
- Extend `tests/test_discovery_dialog.py` — add bitrate-persistence case (PB-13)
- Extend `tests/test_repo.py` — migration test (PB-02) + bitrate field hydration (PB-01)
- Extend `tests/test_player_failover.py` — new queue-ordering case (PB-18)
- No framework install needed — pytest + pytest-qt already in `pyproject.toml`

## Security Domain

Security gate is not triggered for this phase. Justification:

| ASVS Category | Applies | Notes |
|---------------|---------|-------|
| V2 Authentication | no | No auth surfaces touched |
| V3 Session Management | no | n/a |
| V4 Access Control | no | No privilege boundaries changed |
| V5 Input Validation | yes (minor) | `QIntValidator` enforces numeric input in the bitrate cell; `int(text or "0")` at save coerces defensively. Values clamped to 0-9999 by validator. |
| V6 Cryptography | no | No crypto operations |

No hand-rolled validation; `QIntValidator` is the Qt-provided control and `sqlite3` handles SQL param binding via `?` placeholders (already the project convention — verified by reading all `repo.con.execute(...)` calls).

**Threat patterns for SQLite + Qt input:**

| Pattern | STRIDE | Mitigation (already in place) |
|---------|--------|-------------------------------|
| SQL injection via bitrate field | Tampering | `?` placeholders everywhere in `repo.py` and `settings_export.py`; no string concatenation |
| Integer overflow / negative bitrate | Tampering | `QIntValidator(0, 9999, parent)` clamps at input layer; SQL column is `INTEGER` |
| Malformed bitrate in import ZIP | Tampering | `stream.get("bitrate_kbps", 0)` — defensive default prevents KeyError; non-int values would raise but the field is stamped by `int(...)` on export so that's unlikely in practice. Plan should add `int(stream.get("bitrate_kbps", 0) or 0)` for full defense. |

## Pitfalls

### P-1: Export silently drops `bitrate_kbps`

If the plan edits `models.py` and `repo.py` but forgets `settings_export._station_to_dict`, exports will omit the field. On re-import, every stream lands as 0. **Watch task:** task action MUST touch `settings_export.py` lines 101-122 (`_station_to_dict`), NOT just the commit-side SQL.

### P-2: Import crashes on older ZIPs without `bitrate_kbps`

Forgetting `.get("bitrate_kbps", 0)` in both `_insert_station` and `_replace_station` will cause `KeyError` on pre-47 archives. Plan task must explicitly use `.get` (not `data["bitrate_kbps"]`) and specify `0` as the fallback.

### P-3: `order_streams` mutates input

`list.sort(key=...)` vs `sorted(list, key=...)` — use the latter. If `order_streams` mutates, `Station.streams` (the list stored on the model) would be reordered by reference, breaking any caller that expects position-order (notably the Edit Station dialog's populate logic, which currently displays streams in SELECT order from `list_streams`, which is `ORDER BY position`).

### P-4: Empty bitrate cell raises ValueError on save

`int("")` raises `ValueError`. Must be `int(text or "0")`. Mirror the pattern already in place for the Position column at edit_station_dialog.py:678 (`try: position = int(pos_item.text()) except ValueError: position = row + 1`). Either pattern works — `int(text or "0")` is tighter since the validator already rules out non-numeric characters, so the only degenerate case is empty string.

### P-5: QIntValidator on QTableWidget needs a delegate

The naive approach — `item.setFlags(... editable)` + plain `QTableWidgetItem(text)` — gives an editable cell but NO validator. QTableWidget edits via an item delegate; a plain `QTableWidgetItem` does not carry validator state. To enforce D-13 (`QLineEdit` + validator), subclass `QStyledItemDelegate` and override `createEditor` to return `QLineEdit` with `setValidator(QIntValidator(0, 9999, parent))`. Apply with `streams_table.setItemDelegateForColumn(_COL_BITRATE, BitrateDelegate(self))`. Keep the delegate class local to `edit_station_dialog.py`.

### P-6: RadioBrowser save path needs a post-insert update

`insert_station` creates the stream internally via `insert_stream(station_id, url)` — with no metadata. To persist bitrate from a search result without widening `insert_station`'s public signature, follow `aa_import.import_stations_multi`'s pattern: call `insert_station`, then `list_streams(station_id)[0]`, then `update_stream(stream.id, url, label="", quality="", position=1, stream_type="", codec="", bitrate_kbps=bitrate_val)`. Works cleanly because `list_streams` is already ORDER BY position.

## Sources

All findings verified by reading source files in-tree. No external library lookups needed; the phase is a tight additive schema + pure-function change using only stdlib + project conventions.

### Primary (HIGH confidence — direct file reads)

- `musicstreamer/models.py` (46 lines)
- `musicstreamer/repo.py` (455 lines)
- `musicstreamer/player.py` (459 lines)
- `musicstreamer/aa_import.py` (321 lines)
- `musicstreamer/radio_browser.py` (77 lines)
- `musicstreamer/ui_qt/discovery_dialog.py` (493 lines)
- `musicstreamer/ui_qt/edit_station_dialog.py` (717 lines)
- `musicstreamer/settings_export.py` (442 lines)
- `musicstreamer/__main__.py` (partial)
- `tests/test_aa_import.py`, `tests/test_settings_export.py`, `tests/test_edit_station_dialog.py`, `tests/test_player_failover.py`, `tests/test_stream_picker.py`, `tests/test_radio_browser.py` — test-style reference
- `pyproject.toml` (pytest config)
- `.planning/phases/47-.../47-CONTEXT.md` (authoritative user decisions)

### Grep verifications

- `StationStream\(` in `musicstreamer/` → 3 sites (repo.py hydration, __main__.py smoke, discovery_dialog.py preview)
- `asdict` → 0 hits (no hidden dataclass serialization)
- `bitrate` (case-insensitive) in `musicstreamer/` → only `radio_browser.py` docstring + `discovery_dialog.py` UI column (no persistence today)
- `insert_station|insert_stream` → all repo call sites mapped (9 occurrences)

## Assumptions Log

Empty — all claims in this research were verified by reading source in the current working tree. No user confirmation required before planning.

## Open Questions

None. All five research targets from the objective are resolved:

1. ✅ Table name confirmed as `station_streams` (repo.py:51).
2. ✅ Failover hook at `player.py:166` (single-line swap).
3. ✅ RadioBrowser "import module" is actually `discovery_dialog.py::_on_save_row` — CONTEXT's `musicstreamer/radio_browser_import.py` does not exist.
4. ✅ AA tier-map site confirmed at `aa_import.py` (both `fetch_channels_multi` line 153 for codec, and a parallel bitrate map to be added near line 136 `position_map`).
5. ✅ Validation Architecture section delivered (PB-01 through PB-19).

## Metadata

**Confidence breakdown:**
- Standard patterns (ALTER TABLE, dataclass defaults, dict serialization): HIGH — all idioms verified in-tree
- Call-site map: HIGH — every line number verified by direct read
- Failover algorithm: HIGH — D-04 through D-09 are fully specified in CONTEXT; no ambiguity
- RadioBrowser gap (G-2): HIGH — grep confirmed `radio_browser_import.py` does not exist; save path traced end-to-end
- Validation Architecture: HIGH — test framework already in use, all extension points identified

**Research date:** 2026-04-17
**Valid until:** 2026-05-17 (30 days — codebase is stable, phase is tight additive)
