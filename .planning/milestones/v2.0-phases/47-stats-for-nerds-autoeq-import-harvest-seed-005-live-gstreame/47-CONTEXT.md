# Phase 47: Stream bitrate quality ordering - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a numeric `bitrate_kbps` field to `StationStream`, populate it during AA and RadioBrowser imports, and reorder the failover queue by `(codec_rank desc, bitrate_kbps desc)` so higher-quality streams play first. Expose the field in the Edit Station stream table so users can correct/override values.

**Not in scope** (deferred — originally bundled into "Phase 47" on the roadmap, split 2026-04-17):
- SEED-005 stats-for-nerds buffer indicator → **Phase 47.1**
- SEED-007 AutoEQ parametric EQ import → **Phase 47.2**

These are independent features that share no meaningful code with bitrate ordering; they now live in their own phases for cleaner UAT and scope.

</domain>

<decisions>
## Implementation Decisions

### Model / Schema
- **D-01:** Add `bitrate_kbps: int = 0` to `StationStream` dataclass in `musicstreamer/models.py`. Default 0 means "unknown".
- **D-02:** DB migration follows the existing additive pattern in `musicstreamer/repo.py` — a `try: con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0"); except sqlite3.OperationalError: pass` block alongside the other column migrations. No PRAGMA `user_version` bump; the additive pattern is idempotent.
- **D-03:** Keep the existing `quality: str` field. `quality` remains a human-facing label ("hi" / "med" / "low" / custom tags); `bitrate_kbps` is the new numeric sort key. Failover uses bitrate_kbps; UI shows quality label alongside bitrate. Minimal disruption, preserves user custom tags, no migration of existing `quality` values needed.

### Failover Ordering Algorithm
- **D-04:** Sort streams within a station by `(codec_rank desc, bitrate_kbps desc, position asc)`.
- **D-05:** Codec ranks (from ROADMAP): `FLAC=3 > AAC=2 > MP3=1 > other=0`. Unknown/empty codec → rank 0.
- **D-06:** Cross-codec tie at same bitrate: AAC ranks above MP3 (efficiency advantage at equivalent perceptual quality). Covered by the codec_rank.
- **D-07:** **Unknown bitrates (bitrate_kbps == 0) sort LAST.** Streams with known bitrate come first, in `(codec_rank desc, bitrate_kbps desc)` order. Unknowns fall to the bottom, keeping their relative `position asc` order among themselves. Predictable and partial-data-safe.
- **D-08:** The codec_rank function lives in a new module — recommended: `musicstreamer/stream_ordering.py` — exposed as a public `order_streams(streams: list[StationStream]) -> list[StationStream]` and a `codec_rank(codec: str) -> int` helper. Kept out of `models.py` to avoid widening the dataclass file.
- **D-09:** The function is **pure** (no DB access, no mutation) — takes a list, returns a new sorted list. Callers (player.py failover driver, edit dialog preview column if any) pass in streams and use the returned order.

### AA Import
- **D-10:** `aa_import.py` populates `bitrate_kbps` from DI.fm quality tiers exactly as spec'd in the roadmap: `hi=320`, `med=128`, `low=64`. Codec is already "AAC" for DI.fm. Quality field stays set to the tier string ("hi"/"med"/"low") as today.

### RadioBrowser Import
- **D-11:** RadioBrowser API already returns `bitrate: int` per stream. Populate `bitrate_kbps` directly from this field. If `bitrate` is absent or 0, leave `bitrate_kbps=0` (treat as unknown).

### Edit Station Dialog
- **D-12:** Add a 5th column to `streams_table` in `edit_station_dialog.py`. New column layout: **URL | Quality | Codec | Bitrate | Position**. Bitrate is a `QLineEdit` with an `QIntValidator(0, 9999, parent)` to restrict to numeric input. `0` renders as empty string in the cell for readability (and stores as 0 in the model).
- **D-13:** `QTableWidget` cell editor uses the default delegate with a `QLineEdit` + validator. No combo box, no spinner (free-form typing is fastest for the user and covers custom/unusual bitrates like 96 or 192).
- **D-14:** Save path: when the dialog's Save commits changes, read the bitrate column as `int(text or "0")` — empty cell persists as 0 (unknown).

### Claude's Discretion
- Exact file paths for `stream_ordering.py` (could live under `musicstreamer/` top-level or `musicstreamer/player/` subpackage). Lean toward top-level `musicstreamer/stream_ordering.py` to mirror existing `musicstreamer/aa_import.py`, `musicstreamer/settings_export.py` conventions.
- Test file name/location: `tests/test_stream_ordering.py` covering the pure ordering function with table-driven cases (all-known / all-unknown / mixed / same-codec-diff-bitrate / cross-codec / edge cases).
- Whether to add an inline "computed order" preview column to the Edit dialog so users can see how their bitrates will reorder failover. Lean toward **no** — keep the UI simple; failover order is only observed in production behavior.
- Whether the AA import's `bitrate_kbps` population is a per-provider override table (constants) or inline map in `aa_import.py`. Lean toward an inline map near the existing quality-tier code (keeps related logic colocated).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Model + schema
- `musicstreamer/models.py` — `StationStream` dataclass (fields: `url, label, quality, codec, position`); add `bitrate_kbps`.
- `musicstreamer/repo.py` — `db_init` plus the additive ALTER TABLE migration pattern (several existing examples for `stations` columns — mirror for `station_streams`).
- Schema table name: inspect `repo.py db_init` for the actual `station_streams` / `streams` / `station_stream` table name; use that in the migration.

### Failover + player
- `musicstreamer/player.py` — failover queue construction site; where `order_streams` gets called before dispatch.
- Any existing per-stream iteration in `player.py` (order, retry, skip) must be checked against the new ordering contract.

### Import paths
- `musicstreamer/aa_import.py` — DI.fm quality-tier mapping site; add `bitrate_kbps` population alongside the existing `quality` assignment.
- `musicstreamer/radio_browser_import.py` (or wherever RadioBrowser imports live — confirm during research) — maps the API `bitrate` field into `bitrate_kbps`.

### UI
- `musicstreamer/ui_qt/edit_station_dialog.py` — `streams_table` at line 275 (4-column setup); extend to 5 columns, add `QIntValidator` for the new column.

### Prior CONTEXT
- `.planning/phases/39-core-dialogs/39-CONTEXT.md` — earlier decisions about the Edit Station dialog (stream table was introduced there). Verify the bitrate addition doesn't conflict with any prior UI decision.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Additive migration pattern** at `musicstreamer/repo.py` — several `ALTER TABLE ... ADD COLUMN` blocks wrapped in try/except, exactly the shape needed for `bitrate_kbps`.
- **StationStream dataclass** at `musicstreamer/models.py:12` — add one field (`bitrate_kbps: int = 0`), follow the `@dataclass` style already in use.
- **QTableWidget pattern** at `edit_station_dialog.py:275` — already uses `setHorizontalHeaderLabels`, `setAlternatingRowColors`, `setSelectionBehavior`, `setItem`. Extending to 5 columns is mechanical.

### Established Patterns
- Repo returns model dataclasses — the failover driver receives `list[StationStream]` and iterates. The pure `order_streams` function slots in cleanly at the iteration site.
- Tests live under `tests/` with `test_<module>.py` naming; the stream ordering function tests mirror `tests/test_aa_import.py` style (table-driven unit tests, no DB fixture needed for a pure function).

### Integration Points
- **`aa_import.py` quality-tier mapping** — where the new bitrate population lives. Co-located with the existing quality tier logic.
- **`player.py` failover driver** — call site for `order_streams`. Pass the station's streams, iterate in returned order.
- **`edit_station_dialog.py` streams_table** — 5th column. Save path reads the cell and parses to int.

</code_context>

<specifics>
## Specific Ideas

- **Failover algorithm (verbatim from roadmap):** sort `(codec_rank desc, bitrate_kbps desc)` for streams with known bitrate; unknowns (`bitrate_kbps == 0`) come last, in their relative `position asc` order.
- **Codec rank constants:** `FLAC=3, AAC=2, MP3=1, other=0` (case-insensitive match; trim whitespace).
- **AA tier map:** `hi=320, med=128, low=64` (DI.fm AAC; extendable later if other AA providers surface).
- **Edit dialog column order:** URL | Quality | Codec | Bitrate | Position. Bitrate cell uses `QLineEdit` + `QIntValidator(0, 9999, parent)`; empty cell ↔ 0.
- **Module placement:** `musicstreamer/stream_ordering.py` (new module, pure functions only).

</specifics>

<deferred>
## Deferred Ideas

- **SEED-005 stats-for-nerds buffer indicator** — now **Phase 47.1**.
- **SEED-007 AutoEQ parametric EQ import** — now **Phase 47.2**.
- **Per-stream live bitrate measurement (ICY metadata)** — actual bitrate from the stream header vs. stored value. Could augment sort accuracy but requires active playback. Future phase.
- **Auto-detect bitrate on stream add** — probe the URL on import to fill `bitrate_kbps` automatically. Requires network I/O during import flow. Future phase.
- **Per-user "prefer lower bitrate for mobile data"** toggle that inverts the sort — reasonable feature, but user wants higher-first today. Future phase.
- **Quality field cleanup / deprecation** — keep both fields for now (D-03). If `quality` becomes redundant after a future phase, revisit.

</deferred>

---

*Phase: 47-stream-bitrate-quality-ordering*
*Context gathered: 2026-04-17*
