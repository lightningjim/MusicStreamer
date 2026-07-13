---
phase: 89A-channel-avatar-db-migration-storage-layout
plan: 02
type: execute
wave: 2
depends_on:
  - 89A-01
files_modified:
  - musicstreamer/repo.py
  - tests/test_repo.py
autonomous: true
requirements:
  - ART-AVATAR-01
must_haves:
  truths:
    - "After db_init(), PRAGMA table_info(stations) shows channel_avatar_path TEXT, nullable, no DEFAULT"
    - "Running db_init() two or three times on the same connection never raises (idempotent)"
    - "A pre-89a stations schema upgraded via db_init() converges to the same channel_avatar_path schema as a fresh DB, and existing rows keep NULL with data preserved"
    - "Implements locked decisions D-04 (idempotent try/except OperationalError ALTER idiom), D-05 (ALTER lands AFTER the stations_new rebuild block — Pitfall 2 ordering), D-06 (migration + directory ONLY — channel_avatar_path is NOT threaded through models.py Station, row mappers, or save_station() this phase), and D-07 (idempotency + schema-convergence test scope)"
  artifacts:
    - path: "musicstreamer/repo.py"
      provides: "additive ALTER TABLE channel_avatar_path migration in db_init()"
      contains: "channel_avatar_path"
    - path: "tests/test_repo.py"
      provides: "idempotency + schema-convergence migration tests"
      contains: "test_channel_avatar_path_migration_idempotent"
  key_links:
    - from: "musicstreamer/repo.py:db_init"
      to: "stations table"
      via: "ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT"
      pattern: "ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT"
---

<objective>
Add the `channel_avatar_path TEXT` column to the `stations` table via the established
idempotent additive-migration idiom in `repo.py:db_init()` (D-04), placed AFTER the
`stations_new` rebuild block to dodge Pitfall 2 (D-05). Delivers ART-AVATAR-01.

Purpose: Phase 89 needs the column to exist to persist YouTube/Twitch avatar paths. This
plan adds the column nullable (NULL = no avatar) with zero behavior change — the column
sits NULL for every row and is NOT threaded through models.py / mappers / save_station
(D-06, deferred to Phase 89).

Output: one new ALTER block in db_init() and two migration tests (idempotency +
schema-convergence) in test_repo.py.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.4.10/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.4.10/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-PATTERNS.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-RESEARCH.md

<interfaces>
<!-- Key existing shapes the executor mirrors. Extracted from codebase 2026-06-13. -->

repo.py — db_init() additive-migration idiom (three existing post-rebuild ALTER blocks):
  Phase 73 cover_art_source, Phase 82 preferred_stream_id, Phase 83 prerolls_fetched_at.
  Phase 83 block spans L297-311 (comment block + try/con.execute(ALTER)/con.commit()/except
  sqlite3.OperationalError: pass). db_init() ends at L312 (blank line); `def sweep_orphans`
  begins at L314. The new block goes BETWEEN them (after L311, inside db_init).

  The stations_new REBUILD block ends ~L265 ("except sqlite3.OperationalError: pass  # url
  column already gone"). The ALTER must land AFTER the rebuild (Pitfall 2) — i.e. with the
  other three phase blocks, not before L265.

test_repo.py:
  - `repo` fixture L6-13: opens a tmp_path DB, calls db_init(), returns Repo(con). Use repo.con.
  - `_make_bare_con()` L620-624: sqlite3.connect(":memory:") + row_factory + PRAGMA foreign_keys=ON.
  - PRAGMA table_info row tuple: (cid=0, name=1, type=2, notnull=3, dflt_value=4, pk=5).
  - test_preferred_stream_id_migration_idempotent L875-897: EXACT idempotency-test template.
  - test_bitrate_kbps_migration_adds_column L642-678: schema-fixture / convergence template.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add channel_avatar_path ALTER block to db_init() + idempotency test</name>
  <files>musicstreamer/repo.py, tests/test_repo.py</files>
  <read_first>
    - musicstreamer/repo.py L208-265 (stations_new rebuild block — the boundary the ALTER must land AFTER, Pitfall 2)
    - musicstreamer/repo.py L297-314 (Phase 83 prerolls_fetched_at block — direct copy template; db_init end at L312; sweep_orphans at L314)
    - tests/test_repo.py L6-13 (repo fixture) and L875-897 (test_preferred_stream_id_migration_idempotent — PRAGMA assertion template)
  </read_first>
  <behavior>
    - Test: calling db_init(repo.con) two extra times does not raise
    - Test: PRAGMA table_info('stations') has channel_avatar_path with col[2]=="TEXT", col[3]==0 (nullable), col[4] is None (no DEFAULT)
  </behavior>
  <action>
    In musicstreamer/repo.py, insert a new migration block immediately AFTER the Phase 83
    `prerolls_fetched_at` block (after L311's `pass  # column already exists — idempotent`),
    still INSIDE db_init() and BEFORE `def sweep_orphans` at L314. Per D-04/D-05: a comment
    block citing Phase 89A D-04/D-05 and Pitfall 2 (mirror the Phase 82/83 comment wording —
    nullable TEXT no DEFAULT, NULL means no avatar stored, existing rows backfill automatically,
    MUST land after the stations_new rebuild), then
    `try: con.execute("ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT") / con.commit() /
    except sqlite3.OperationalError: pass  # column already exists — idempotent`. The DDL string
    is exactly `ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT` — TEXT, no DEFAULT, no
    NOT NULL. Do NOT touch the stations_new rebuild block, models.py, row mappers, or save_station
    (D-06 — migration ONLY).

    In tests/test_repo.py, append `test_channel_avatar_path_migration_idempotent(repo)` mirroring
    test_preferred_stream_id_migration_idempotent (L875-897): call db_init(repo.con) twice more
    (no raise), then PRAGMA table_info('stations'), build by_name = {row[1]: row}, assert
    "channel_avatar_path" present, then col[2]=="TEXT", col[3]==0, col[4] is None.
  </action>
  <verify>
    <automated>uv run --with pytest pytest "tests/test_repo.py::test_channel_avatar_path_migration_idempotent" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT" musicstreamer/repo.py` matches exactly one line.
    - That line appears AFTER the Phase 83 prerolls_fetched_at block: `grep -n "prerolls_fetched_at\|channel_avatar_path" musicstreamer/repo.py` shows prerolls_fetched_at line number(s) LESS than the channel_avatar_path ALTER line number.
    - The ALTER line appears BEFORE `def sweep_orphans`: the channel_avatar_path line number is less than the `def sweep_orphans` line number.
    - `test_channel_avatar_path_migration_idempotent` passes: column is TEXT (col[2]), nullable (col[3]==0), no DEFAULT (col[4] is None), and triple db_init() does not raise.
  </acceptance_criteria>
  <done>db_init() adds channel_avatar_path TEXT after the rebuild block; the idempotency test confirms nullable TEXT no DEFAULT and double/triple db_init() safety.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Schema-convergence + data-preservation test (D-07b)</name>
  <files>tests/test_repo.py</files>
  <read_first>
    - tests/test_repo.py L620-624 (_make_bare_con helper) and L642-678 (test_bitrate_kbps_migration_adds_column — pre-migration schema fixture shape)
    - .planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-PATTERNS.md L187-213 (pre-89a stations DDL to use, including the station_streams FK caveat)
    - musicstreamer/repo.py L88-200 (db_init CREATE TABLE statements — to confirm which tables the legacy fixture must pre-create so db_init() runs cleanly on it)
  </read_first>
  <behavior>
    - Test: a fresh _make_bare_con() + db_init() captures the target channel_avatar_path schema (type, notnull, dflt_value)
    - Test: a pre-89a stations table (channel_avatar_path absent) after db_init() converges to the same channel_avatar_path schema tuple as fresh
    - Test: the pre-existing 'ExistingFM' row survives with channel_avatar_path IS NULL
  </behavior>
  <action>
    In tests/test_repo.py, append `test_channel_avatar_path_schema_convergence()` (no `repo`
    fixture — uses _make_bare_con per RESEARCH §Concrete Test Specifications Test 2). Build a
    fresh DB via `_make_bare_con()` + `db_init()`, capture fresh_cols = {name: (type, notnull,
    dflt_value)} from PRAGMA table_info('stations'); assert channel_avatar_path present. Then
    build a legacy connection via `_make_bare_con()` and `executescript(...)` creating a pre-89a
    stations table WITHOUT channel_avatar_path (use the DDL in PATTERNS.md L187-213, columns
    through prerolls_fetched_at), inserting one `('ExistingFM')` row. IMPORTANT: before calling
    db_init() on the legacy connection, confirm by reading repo.py db_init() which tables it
    expects to already exist or creates via CREATE TABLE IF NOT EXISTS — pre-create any table
    (e.g. station_streams referenced by the preferred_stream_id FK) that db_init()'s migration
    path needs so the run does not error on the legacy fixture. Assert channel_avatar_path absent
    pre-migration, run db_init(legacy_con), then assert
    migrated_cols["channel_avatar_path"] == fresh_cols["channel_avatar_path"] (convergence) and
    that the ExistingFM row still exists with channel_avatar_path IS NULL (data preserved).
  </action>
  <verify>
    <automated>uv run --with pytest pytest "tests/test_repo.py::test_channel_avatar_path_schema_convergence" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def test_channel_avatar_path_schema_convergence" tests/test_repo.py` matches exactly one line.
    - The test asserts schema equality between fresh and upgraded DBs for channel_avatar_path (type/notnull/dflt_value tuple) AND that the pre-existing row's channel_avatar_path is None.
    - `test_channel_avatar_path_schema_convergence` passes via the verify command above.
    - Full quick suite stays green: `uv run --with pytest pytest tests/test_repo.py tests/test_paths.py -x -q` passes.
  </acceptance_criteria>
  <done>Schema convergence (fresh DB == upgraded pre-89a DB) and data preservation (existing row NULL) are proven; ROADMAP Success Criterion 2 rollback/convergence intent satisfied.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No new trust boundary is crossed. The migration adds a nullable TEXT column via a constant
DDL string (no interpolation, no user input). No network, no privileged operation. The column
accepts NULL only in this phase — no user-controlled data is written until Phase 89.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89A-02 | Tampering | repo.py:db_init ALTER TABLE | accept | DDL is a fixed string literal with no parameter interpolation; SQL injection is not reachable (no user input). Additive nullable column does not alter existing data. No control required (RESEARCH §Security Domain: no applicable ASVS L1 controls). |

No high/medium threats: additive nullable column with a constant DDL, no user-controlled data
until Phase 89, no network. ASVS L1 finds no applicable controls for this plan.
</threat_model>

<verification>
- `uv run --with pytest pytest tests/test_repo.py -x -q` passes (both new migration tests green, no regressions).
- `grep -n "ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT" musicstreamer/repo.py` returns exactly one match, positioned after the prerolls_fetched_at block and before `def sweep_orphans`.
- No edits to musicstreamer/models.py, row→Station mappers, or save_station() (D-06): `git diff --name-only` shows only repo.py and tests/test_repo.py for this plan.
</verification>

<success_criteria>
- ART-AVATAR-01 satisfied: stations gains channel_avatar_path TEXT via idempotent additive migration; existing rows default to NULL.
- ROADMAP Success Criterion 1 satisfied: PRAGMA table_info(stations) shows the new TEXT column with NULL for all existing rows; existing data unchanged.
- ROADMAP Success Criterion 2 satisfied: double-run idempotency proven; schema convergence (fresh == upgraded) proven.
- Zero behavior change beyond the column (D-06 — no models/mapper/save_station changes).
</success_criteria>

<output>
Create `.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-02-SUMMARY.md` when done.
</output>
