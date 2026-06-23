import logging
import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite, StationStream
from musicstreamer import paths


# Phase 80 / BUG-10: module logger (first logger in repo.py).
# Surfaced at INFO via __main__.py per-logger setLevel — see Plan 80-02.
_log = logging.getLogger(__name__)


# Phase 80 / BUG-10 / D-11: module-level sentinel throttling the PRAGMA
# drift-guard WARN to once per session. Reset for tests via
# _reset_pragma_drift_sentinel_for_tests() (Pitfall 3: pytest reuses the
# imported module across all tests in a session, so without an explicit
# reset the sentinel leaks and masks real drift in later tests).
_pragma_drift_logged: bool = False


def _reset_pragma_drift_sentinel_for_tests() -> None:
    """Test-only helper: re-arm the drift-guard WARN throttle.

    The module-level ``_pragma_drift_logged`` sentinel persists across the
    pytest session (Phase 80 RESEARCH Pitfall 3). Tests that exercise the
    drift-guard log surface must call this helper in their setup to ensure
    the WARN fires deterministically rather than being swallowed by a flip
    in an earlier test.

    The ``_for_tests`` suffix is an intentional grep-discoverability
    convention — it makes the test-only nature of this helper obvious to
    any future reader scanning ``repo.py`` for production API.
    """
    global _pragma_drift_logged
    _pragma_drift_logged = False


# Phase 73 WR-03: valid values for the `cover_art_source` column. The
# Station dataclass declares this as a Literal[...] but Python does not
# enforce Literal at runtime — a typo in any caller would persist silently
# and surface only as a downstream bug (e.g. EditStationDialog combobox
# falling through to index 0 with no error). Validate at the write
# boundary so bad values never reach the DB.
VALID_COVER_ART_SOURCES: frozenset[str] = frozenset({"auto", "itunes_only", "mb_only"})


def db_connect() -> sqlite3.Connection:
    """Return a SQLite connection with foreign-key enforcement enabled.

    The PRAGMA-foreign-keys-ON line below is load-bearing: every
    ``ON DELETE CASCADE`` in :func:`db_init`'s schema (``station_streams``
    on ``stations.id``; ``station_siblings`` on ``stations.id`` via both
    ``a_id`` and ``b_id``) only fires when this PRAGMA is set on the
    connection issuing the parent DELETE. SQLite defaults the PRAGMA to
    OFF per connection — so removing this line would silently leak orphan
    rows on every station deletion (BUG-10; Phase 74 F-07-03 Synphaera
    ghosts).

    Anyone needing a SQLite connection MUST go through this function; a
    source-grep regression test
    (``tests/test_db_connect_is_sole_connection_factory.py``, landing in
    Plan 80-04) asserts that no other call site of ``sqlite3.connect(...)``
    exists in the production tree.

    Caller owns the connection lifecycle and is responsible for calling
    ``con.close()`` — matching ``sweep_orphans``'s contract. Several
    pre-existing ``Repo(db_connect())`` call sites in ``aa_import.py``,
    ``soma_import.py``, ``ui_qt/import_dialog.py``, ``ui_qt/main_window.py``,
    and ``ui_qt/settings_import_dialog.py`` orphan the connection today
    (WR-03 from the Phase 80 review). A follow-up phase should introduce a
    ``with db_session() as repo:`` context-manager wrapper and migrate
    those call sites.
    """
    global _pragma_drift_logged
    con = sqlite3.connect(paths.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    if not _pragma_drift_logged:
        if con.execute("PRAGMA foreign_keys").fetchone()[0] == 0:
            _log.warning(
                "PRAGMA foreign_keys is OFF after SET — drift detected"
            )
        _pragma_drift_logged = True
    return con


def db_init(con: sqlite3.Connection):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS providers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS stations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          provider_id INTEGER,
          tags TEXT DEFAULT '',                 -- comma-separated for now (simple step)
          station_art_path TEXT,                -- relative path under assets/
          album_fallback_path TEXT,             -- relative path under assets/
          created_at TEXT DEFAULT (datetime('now')),
          updated_at TEXT DEFAULT (datetime('now')),
          FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );

        CREATE TRIGGER IF NOT EXISTS stations_updated_at
        AFTER UPDATE ON stations
        BEGIN
          UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
        END;

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT NOT NULL,
            provider_name TEXT NOT NULL DEFAULT '',
            track_title TEXT NOT NULL,
            genre TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            UNIQUE(station_name, track_title)
        );

        CREATE TABLE IF NOT EXISTS station_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            quality TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 1,
            stream_type TEXT NOT NULL DEFAULT '',
            codec TEXT NOT NULL DEFAULT '',
            bitrate_kbps INTEGER NOT NULL DEFAULT 0,
            sample_rate_hz INTEGER NOT NULL DEFAULT 0,
            bit_depth INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS station_siblings (
          a_id INTEGER NOT NULL,
          b_id INTEGER NOT NULL,
          FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
          FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
          UNIQUE(a_id, b_id),
          CHECK(a_id < b_id)
        );

        -- Phase 83 D-01/D-15 — SomaFM station prerolls. Additive table mirroring
        -- the station_streams shape (Phase 47); FK ON DELETE CASCADE cleans up
        -- rows when the parent station is deleted (also keeps Phase 74 re-import
        -- wipe-and-replace flow clean per RESEARCH §"Re-import edge case").
        -- Idempotent via CREATE TABLE IF NOT EXISTS — second db_init is a no-op.
        CREATE TABLE IF NOT EXISTS station_prerolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
        """
    )
    con.commit()

    try:
        con.execute("ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute("ALTER TABLE stations ADD COLUMN last_played_at TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute("ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute("ALTER TABLE station_streams ADD COLUMN sample_rate_hz INTEGER NOT NULL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute("ALTER TABLE station_streams ADD COLUMN bit_depth INTEGER NOT NULL DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # table already exists

    # Migration: if stations table still has url column, migrate data and drop column
    try:
        con.execute("SELECT url FROM stations LIMIT 1")
        # url column exists — migrate to station_streams then recreate table without url
        con.execute(
            """
            INSERT INTO station_streams (station_id, url, position)
            SELECT id, url, 1 FROM stations
            WHERE url != '' AND url IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM station_streams ss WHERE ss.station_id = stations.id
            )
            """
        )
        con.commit()

        # Recreate stations table without url column (SQLite has no DROP COLUMN before 3.35)
        con.executescript(
            """
            PRAGMA foreign_keys = OFF;

            CREATE TABLE stations_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider_id INTEGER,
                tags TEXT DEFAULT '',
                station_art_path TEXT,
                album_fallback_path TEXT,
                icy_disabled INTEGER NOT NULL DEFAULT 0,
                last_played_at TEXT,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
            );

            INSERT INTO stations_new (id, name, provider_id, tags, station_art_path,
                album_fallback_path, icy_disabled, last_played_at, created_at, updated_at)
            SELECT id, name, provider_id, tags, station_art_path,
                album_fallback_path, icy_disabled, last_played_at, created_at, updated_at
            FROM stations;

            DROP TABLE stations;

            ALTER TABLE stations_new RENAME TO stations;

            CREATE TRIGGER IF NOT EXISTS stations_updated_at
            AFTER UPDATE ON stations
            BEGIN
              UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
            END;

            PRAGMA foreign_keys = ON;
            """
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # url column already gone — migration already ran

    # Phase 73 D-01/D-05 — per-station cover-art source routing preference.
    # RESEARCH Pitfall 8: this ALTER MUST land AFTER the legacy URL-column rebuild
    # block above, because the rebuild's CREATE TABLE stations_new / INSERT SELECT
    # do NOT know about cover_art_source. Placing the ALTER here ensures the
    # column lands on the rebuilt table (or on a fresh CREATE TABLE IF NOT EXISTS
    # stations if no legacy rebuild was needed). Idempotent across re-runs via
    # the try/except sqlite3.OperationalError idiom (matches repo.py:79-94 shape).
    try:
        con.execute(
            "ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent; existing rows backfilled via DEFAULT

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

    # Phase 89.1 D-11 — provider-level channel avatar; nullable TEXT no DEFAULT.
    # providers has NO legacy rebuild block (unlike stations — see Phase 73/82/83/89A
    # ordering comments). Confirmed by grep: zero hits for 'providers_new' in db_init.
    # Idempotent via the same try/except OperationalError idiom as above.
    try:
        con.execute("ALTER TABLE providers ADD COLUMN avatar_path TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 96 D-01 — per-station opt-in live URL re-sync flag; INTEGER NOT NULL DEFAULT 0.
    # Existing rows default to 0 (OFF) automatically. MUST land AFTER the legacy
    # URL-column rebuild block (Pitfall 8): the rebuild's CREATE TABLE stations_new /
    # INSERT SELECT does not carry dynamically-added columns, so placing the ALTER here
    # ensures the column lands on the rebuilt (or fresh) table. Idempotent via the same
    # try/except sqlite3.OperationalError idiom as the Phase 73/82/83/89A blocks above.
    try:
        con.execute(
            "ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 96 D-03 — per-station title anchor from live stream; nullable TEXT no DEFAULT.
    # NULL means flag is ON but anchor not yet captured. MUST land AFTER the legacy
    # URL-column rebuild block for the same Pitfall 8 reason as D-01 above.
    try:
        con.execute("ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 96 D-04 — per-provider channel scan URL; nullable TEXT no DEFAULT.
    # providers has NO legacy rebuild block — safe to add at any position after
    # the Phase 89.1 providers ALTER above. Idempotent via same try/except idiom.
    try:
        con.execute("ALTER TABLE providers ADD COLUMN channel_scan_url TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent

    # Phase 89.1 D-01/D-02/D-03: one-time idempotent backfill.
    # Copy the most-recently-updated per-station PNG to the provider-keyed location
    # and record the path in providers.avatar_path. Old per-station files deleted
    # only after providers.avatar_path is committed (Pitfall 3 — shutil.copy2 not
    # os.rename; source file survives a mid-backfill crash).
    # Skips stations with provider_id IS NULL (WHERE clause excludes them).
    # NOT EXISTS guard on p.avatar_path ensures idempotency.
    # Guard: only run if the stations table has both channel_avatar_path and
    # provider_id columns (legacy test-fixture schemas may lack them; the
    # backfill is a no-op on such schemas).
    _stations_cols = {
        row[1]
        for row in con.execute("PRAGMA table_info('stations')").fetchall()
    }
    _backfill_eligible = (
        "channel_avatar_path" in _stations_cols and "provider_id" in _stations_cols
    )
    if _backfill_eligible:
        import os as _os, shutil as _shutil
        from musicstreamer import paths as _bfpaths  # safe: no Qt dependency

        _avatar_dir = _bfpaths.channel_avatars_dir()
        _bf_rows = con.execute(
            """
            SELECT s.provider_id,
                   s.channel_avatar_path,
                   s.id AS station_id
            FROM   stations s
            WHERE  s.channel_avatar_path IS NOT NULL
              AND  s.provider_id IS NOT NULL
              AND  s.updated_at = (
                       SELECT MAX(s2.updated_at)
                       FROM   stations s2
                       WHERE  s2.provider_id = s.provider_id
                         AND  s2.channel_avatar_path IS NOT NULL
                   )
              AND  NOT EXISTS (
                       SELECT 1 FROM providers p
                       WHERE p.id = s.provider_id AND p.avatar_path IS NOT NULL
                   )
            ORDER BY s.provider_id, s.id DESC
            """
        ).fetchall()
        _seen: set = set()
        for _row in _bf_rows:
            _pid = _row[0]
            if _pid in _seen:
                continue  # take only the first (best) row per provider
            _seen.add(_pid)
            _src = _os.path.join(_bfpaths.data_dir(), _row[1])
            if not _os.path.isfile(_src):
                continue  # avatar missing on disk — skip this provider (T-89.1-04)
            _dst = _os.path.join(_avatar_dir, f"{_pid}.png")
            _prov_rel = _os.path.relpath(_dst, _bfpaths.data_dir())
            try:
                _os.makedirs(_avatar_dir, exist_ok=True)
                if _os.path.abspath(_src) != _os.path.abspath(_dst):
                    _shutil.copy2(_src, _dst)  # copy2 not rename: crash-safe (T-89.1-02 / Pitfall 3)
                # If src == dst (station_id == provider_id), file is already in place — just update DB.
            except OSError:
                continue  # skip provider on copy failure — don't abort db_init
            con.execute(
                "UPDATE providers SET avatar_path = ? WHERE id = ?",
                (_prov_rel, _pid),
            )
            con.commit()

        # Clean up per-station files whose provider now has a committed avatar (D-01).
        # EXCLUDE paths that ARE the provider avatar (s.channel_avatar_path == p.avatar_path)
        # — this prevents deleting the newly-written provider-keyed file when a station's
        # legacy path happened to match (e.g. station_id == provider_id on a fresh DB).
        # OSError swallowed — file may already be gone (idempotent on double-run).
        for _cr in con.execute(
            """
            SELECT s.channel_avatar_path
            FROM   stations s
            JOIN   providers p ON p.id = s.provider_id
            WHERE  s.channel_avatar_path IS NOT NULL
              AND  p.avatar_path IS NOT NULL
              AND  s.channel_avatar_path != p.avatar_path
            """
        ).fetchall():
            try:
                _os.unlink(_os.path.join(_bfpaths.data_dir(), _cr[0]))
            except OSError:
                pass  # already gone — idempotent


def sweep_orphans(con: sqlite3.Connection) -> None:
    """Delete orphan FK-child rows and INFO-log per-table counts when N>0.

    Heals orphan rows left behind by manual ``sqlite3``-shell DELETEs that
    bypassed :func:`db_connect`'s PRAGMA enforcement — the failure mode
    that produced the Phase 74 F-07-03 ``Synphaera`` ghosts (``station_streams``
    rows whose parent station was deleted outside the app, defeating
    dedup-by-URL on re-import).

    Runs on every app start; sub-millisecond when N=0; SILENT on N=0
    (D-04 — only emit the INFO log line when at least one table had a
    positive rowcount).

    Per D-05, only the two real FK-cascade child tables are swept:
    ``station_streams`` (cascade on ``stations.id``) and
    ``station_siblings`` (cascade on ``stations.id`` via both ``a_id`` and
    ``b_id`` columns — swept symmetrically with a single DELETE per D-07).

    ``favorites`` is intentionally excluded (D-06): it has no FK, uses
    ``TEXT station_name``, and v1.3 FAVES-01..04 deliberately persists
    track titles after a station is deleted (listening history survives
    station turnover). Sweeping it would silently change documented
    behavior.

    ``stations.provider_id`` orphans are out of scope (D-08): the column
    is declared ``ON DELETE SET NULL`` (not ``CASCADE``); a dangling
    ``provider_id`` is the documented graceful-degrade path, not an
    orphan.

    Caller owns the connection lifecycle — this function does NOT close
    ``con``.
    """
    cur1 = con.execute(
        "DELETE FROM station_streams WHERE station_id NOT IN "
        "(SELECT id FROM stations)"
    )
    cur2 = con.execute(
        "DELETE FROM station_siblings WHERE a_id NOT IN "
        "(SELECT id FROM stations) OR b_id NOT IN (SELECT id FROM stations)"
    )
    if cur1.rowcount > 0 or cur2.rowcount > 0:
        _log.info(
            "sweep_orphans: station_streams=%d station_siblings=%d",
            cur1.rowcount,
            cur2.rowcount,
        )
    con.commit()


class Repo:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def list_providers(self) -> List[Provider]:
        rows = self.con.execute(
            "SELECT id, name, channel_scan_url FROM providers ORDER BY name"
        ).fetchall()
        return [
            Provider(id=r["id"], name=r["name"], channel_scan_url=r["channel_scan_url"])
            for r in rows
        ]

    def ensure_provider(self, name: str) -> Optional[int]:
        name = (name or "").strip()
        if not name:
            return None
        self.con.execute("INSERT OR IGNORE INTO providers(name) VALUES (?)", (name,))
        row = self.con.execute("SELECT id FROM providers WHERE name = ?", (name,)).fetchone()
        self.con.commit()
        return int(row["id"]) if row else None

    def list_streams(self, station_id: int) -> List[StationStream]:
        rows = self.con.execute(
            "SELECT * FROM station_streams WHERE station_id=? ORDER BY position", (station_id,)
        ).fetchall()
        return [StationStream(id=r["id"], station_id=r["station_id"], url=r["url"],
                label=r["label"], quality=r["quality"], position=r["position"],
                stream_type=r["stream_type"], codec=r["codec"],
                bitrate_kbps=r["bitrate_kbps"],
                sample_rate_hz=r["sample_rate_hz"], bit_depth=r["bit_depth"]) for r in rows]

    def insert_stream(self, station_id: int, url: str, label: str = "",
                      quality: str = "", position: int = 1,
                      stream_type: str = "", codec: str = "",
                      bitrate_kbps: int = 0,
                      sample_rate_hz: int = 0, bit_depth: int = 0) -> int:
        cur = self.con.execute(
            "INSERT INTO station_streams(station_id,url,label,quality,position,stream_type,codec,bitrate_kbps,sample_rate_hz,bit_depth) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (station_id, url, label, quality, position, stream_type, codec, bitrate_kbps,
             sample_rate_hz, bit_depth))
        self.con.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # Phase 83 D-01/D-03 — SomaFM preroll CRUD.
    # ------------------------------------------------------------------

    def list_prerolls(self, station_id: int) -> List[str]:
        """Return preroll URLs for the station in ``position`` order.

        Empty list if the station has no prerolls (the majority of SomaFM
        channels — live audit 2026-05-22: 25 of 46 SomaFM channels have an
        empty preroll[] array). The ORDER BY position is load-bearing —
        Player.play uses ``random.choice`` on the returned list (Plan 83-03),
        but other callers expect deterministic position-order iteration.
        """
        rows = self.con.execute(
            "SELECT url FROM station_prerolls WHERE station_id = ? ORDER BY position",
            (station_id,),
        ).fetchall()
        return [r["url"] for r in rows]

    def insert_preroll(self, station_id: int, url: str, position: int) -> int:
        """Insert one preroll row and return the new row id.

        Phase 83 D-01/D-02. Defense in depth at the persistence boundary
        (RESEARCH §Security Domain ASVS V5 Input Validation):

        - **T-83-01 (Tampering):** reject non-HTTP(S) URL schemes. The
          SomaFM importer's ``_safe_urlopen_request`` is the primary gate,
          but the Repo layer is the last gate before bytes hit SQLite —
          a hostile / compromised SomaFM response that injects
          ``file:///`` or ``javascript:`` URLs would otherwise persist and
          later be fed to ``playbin3``'s souphttpsrc.
        - **T-83-02 (DoS):** cap ``position`` at 50. The live SomaFM API
          maximum is 5 prerolls per channel; 50 is 10× headroom. Defends
          against a hostile API response that injects 1M preroll entries.
        - **T-83-03 (SQLi):** parameterized query — same idiom as every
          other Repo method.
        """
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                f"insert_preroll: refusing non-HTTP(S) scheme: {url!r}"
            )
        if position > 50:
            raise ValueError(
                f"insert_preroll: per-channel cap is 50; got position={position}"
            )
        cur = self.con.execute(
            "INSERT INTO station_prerolls(station_id, url, position) VALUES (?, ?, ?)",
            (station_id, url, position),
        )
        self.con.commit()
        return int(cur.lastrowid)

    def update_stream(self, stream_id: int, url: str, label: str,
                      quality: str, position: int, stream_type: str, codec: str,
                      bitrate_kbps: int = 0,
                      sample_rate_hz: int = 0, bit_depth: int = 0):
        self.con.execute(
            "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=?,bitrate_kbps=?,sample_rate_hz=?,bit_depth=? WHERE id=?",
            (url, label, quality, position, stream_type, codec, bitrate_kbps,
             sample_rate_hz, bit_depth, stream_id))
        self.con.commit()

    def delete_stream(self, stream_id: int):
        self.con.execute("DELETE FROM station_streams WHERE id=?", (stream_id,))
        self.con.commit()

    def add_sibling_link(self, a_id: int, b_id: int) -> None:
        lo, hi = min(a_id, b_id), max(a_id, b_id)
        self.con.execute(
            "INSERT OR IGNORE INTO station_siblings(a_id, b_id) VALUES (?, ?)",
            (lo, hi),
        )
        self.con.commit()

    def remove_sibling_link(self, a_id: int, b_id: int) -> None:
        lo, hi = min(a_id, b_id), max(a_id, b_id)
        self.con.execute(
            "DELETE FROM station_siblings WHERE a_id = ? AND b_id = ?",
            (lo, hi),
        )
        self.con.commit()

    def list_sibling_links(self, station_id: int) -> list[int]:
        rows = self.con.execute(
            "SELECT b_id AS sid FROM station_siblings WHERE a_id = ? "
            "UNION "
            "SELECT a_id AS sid FROM station_siblings WHERE b_id = ?",
            (station_id, station_id),
        ).fetchall()
        return [r["sid"] for r in rows]

    def reorder_streams(self, station_id: int, ordered_ids: List[int]):
        for pos, sid in enumerate(ordered_ids, 1):
            self.con.execute("UPDATE station_streams SET position=? WHERE id=? AND station_id=?",
                             (pos, sid, station_id))
        self.con.commit()


    def prune_streams(self, station_id: int, keep_ids: List[int]) -> None:
        """Delete all station_streams rows for station_id whose id is not in keep_ids.

        Called by EditStationDialog._on_save after building ordered_ids so that
        streams the user removed from the UI table are actually deleted from the DB.
        If keep_ids is empty (user removed all streams), all rows for the station
        are deleted — that is an intentional edit, not an accident, so we honour it.
        """
        existing = [
            r[0] for r in self.con.execute(
                "SELECT id FROM station_streams WHERE station_id=?", (station_id,)
            ).fetchall()
        ]
        keep_set = set(keep_ids)
        for sid in existing:
            if sid not in keep_set:
                self.con.execute("DELETE FROM station_streams WHERE id=?", (sid,))
        self.con.commit()

    def get_preferred_stream_url(self, station_id: int, preferred_quality: str = "") -> str:
        if preferred_quality:
            row = self.con.execute(
                "SELECT url FROM station_streams WHERE station_id=? AND quality=? ORDER BY position LIMIT 1",
                (station_id, preferred_quality)).fetchone()
            if row:
                return row["url"]
        row = self.con.execute(
            "SELECT url FROM station_streams WHERE station_id=? ORDER BY position LIMIT 1",
            (station_id,)).fetchone()
        return row["url"] if row else ""

    def list_stations(self) -> List[Station]:
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE
            """
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                Station(
                    id=r["id"],
                    name=r["name"],
                    provider_id=r["provider_id"],
                    provider_name=r["provider_name"],
                    tags=r["tags"] or "",
                    station_art_path=r["station_art_path"],
                    album_fallback_path=r["album_fallback_path"],
                    icy_disabled=bool(r["icy_disabled"]),
                    cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
                    last_played_at=r["last_played_at"],
                    is_favorite=bool(r["is_favorite"]),
                    preferred_stream_id=r["preferred_stream_id"],
                    streams=self.list_streams(r["id"]),
                    prerolls=self.list_prerolls(r["id"]),                 # Phase 83 D-01/D-03
                    prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
                    channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
                    provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
                    live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
                    live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
                )
            )
        return out

    def create_station(self) -> int:
        cur = self.con.execute(
            "INSERT INTO stations(name) VALUES ('New Station')"
        )
        self.con.commit()
        return int(cur.lastrowid)

    def get_station(self, station_id: int) -> Station:
        r = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.id = ?
            """,
            (station_id,),
        ).fetchone()
        if not r:
            raise ValueError("Station not found")
        return Station(
            id=r["id"],
            name=r["name"],
            provider_id=r["provider_id"],
            provider_name=r["provider_name"],
            tags=r["tags"] or "",
            station_art_path=r["station_art_path"],
            album_fallback_path=r["album_fallback_path"],
            icy_disabled=bool(r["icy_disabled"]),
            cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
            last_played_at=r["last_played_at"],
            is_favorite=bool(r["is_favorite"]),
            preferred_stream_id=r["preferred_stream_id"],
            streams=self.list_streams(station_id),
            prerolls=self.list_prerolls(station_id),               # Phase 83 D-01/D-03
            prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
            channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
            provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
            live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
            live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
        )

    def delete_station(self, station_id: int):
        self.con.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        self.con.commit()

    def update_station(
        self,
        station_id: int,
        name: str,
        provider_id: Optional[int],
        tags: str,
        station_art_path: Optional[str],
        album_fallback_path: Optional[str],
        icy_disabled: bool = False,
        cover_art_source: str = "auto",  # Phase 73 D-05 — keyword default
    ):
        """Update the editable columns on a station row.

        Phase 73 D-05: `cover_art_source` is a keyword-default arg appended
        AFTER `icy_disabled` so existing 7-positional-arg callers
        (edit_station_dialog.py:1393-1401, current as of Plan 02) keep their
        positional signature intact. The trade-off: a caller that omits the
        kwarg silently RESETS the column to 'auto'. This is intentional and
        locked by test_repo.test_update_station_omitting_cover_art_source_resets_to_auto
        so Plan 04's EditStationDialog implementation cannot silently regress
        — it MUST always pass the kwarg.

        WR-03: validate cover_art_source at the write boundary. The
        Station dataclass Literal hint is annotation-only and not enforced
        at runtime; a typo would silently persist and surface as a UX bug
        (the dialog combo's index-lookup loop falls through to index 0,
        making the user think their preference is 'auto' when it's
        actually unparseable). Raise ValueError so callers see the bug
        immediately at save time.
        """
        if cover_art_source not in VALID_COVER_ART_SOURCES:
            raise ValueError(
                f"cover_art_source must be one of "
                f"{sorted(VALID_COVER_ART_SOURCES)}; got {cover_art_source!r}"
            )
        self.con.execute(
            """
            UPDATE stations
            SET name = ?, provider_id = ?, tags = ?,
                station_art_path = ?, album_fallback_path = ?, icy_disabled = ?,
                cover_art_source = ?
            WHERE id = ?
            """,
            (name, provider_id, tags, station_art_path, album_fallback_path,
             int(icy_disabled), cover_art_source, station_id),
        )
        self.con.commit()

    def update_last_played(self, station_id: int):
        self.con.execute(
            "UPDATE stations SET last_played_at = strftime('%Y-%m-%dT%H:%M:%f', 'now') WHERE id = ?",
            (station_id,),
        )
        self.con.commit()

    def set_preferred_stream(self, station_id: int, stream_id: Optional[int]) -> None:
        """Phase 82 D-02: persist the user's stream pick. None clears the pick."""
        self.con.execute(
            "UPDATE stations SET preferred_stream_id = ? WHERE id = ?",
            (stream_id, station_id),
        )
        self.con.commit()

    def set_prerolls_fetched_at(self, station_id: int, epoch_seconds: int) -> None:
        """Phase 83 D-04: marks a SomaFM station as 'fetched' so the lazy backfill
        gate does not re-fetch. Set on both happy path (>=1 preroll) and 0-preroll
        path so legitimately-empty channels (Seven Inch Soul etc.) do not hammer
        the API on every Play press."""
        self.con.execute(
            "UPDATE stations SET prerolls_fetched_at = ? WHERE id = ?",
            (epoch_seconds, station_id),
        )
        self.con.commit()

    def list_recently_played(self, n: int = 5) -> List[Station]:
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.last_played_at IS NOT NULL
            ORDER BY s.last_played_at DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()
        return [
            Station(
                id=r["id"],
                name=r["name"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
                last_played_at=r["last_played_at"],
                is_favorite=bool(r["is_favorite"]),
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),
                prerolls=self.list_prerolls(r["id"]),                 # Phase 83 D-01/D-03
                prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
                channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
                provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
                live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
                live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
            )
            for r in rows
        ]

    def get_setting(self, key: str, default: str) -> str:
        row = self.con.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.con.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (key, value),
        )
        self.con.commit()

    def add_favorite(self, station_name: str, provider_name: str,
                     track_title: str, genre: str) -> None:
        self.con.execute(
            "INSERT OR IGNORE INTO favorites(station_name, provider_name, track_title, genre) "
            "VALUES (?, ?, ?, ?)",
            (station_name, provider_name or "", track_title, genre or ""),
        )
        self.con.commit()

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        self.con.execute(
            "DELETE FROM favorites WHERE station_name = ? AND track_title = ?",
            (station_name, track_title),
        )
        self.con.commit()

    def list_favorites(self) -> list[Favorite]:
        rows = self.con.execute(
            "SELECT id, station_name, provider_name, track_title, genre, created_at "
            "FROM favorites ORDER BY created_at DESC"
        ).fetchall()
        return [
            Favorite(
                id=r["id"],
                station_name=r["station_name"],
                provider_name=r["provider_name"],
                track_title=r["track_title"],
                genre=r["genre"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        row = self.con.execute(
            "SELECT 1 FROM favorites WHERE station_name = ? AND track_title = ?",
            (station_name, track_title),
        ).fetchone()
        return row is not None

    def station_exists_by_url(self, url: str) -> bool:
        row = self.con.execute(
            "SELECT 1 FROM station_streams WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int:
        provider_id = self.ensure_provider(provider_name) if provider_name else None
        cur = self.con.execute(
            "INSERT INTO stations(name, provider_id, tags) VALUES (?, ?, ?)",
            (name, provider_id, tags or ""),
        )
        self.con.commit()
        station_id = int(cur.lastrowid)
        if url:
            self.insert_stream(station_id, url)
        return station_id

    def set_station_favorite(self, station_id: int, is_favorite: bool) -> None:
        self.con.execute(
            "UPDATE stations SET is_favorite = ? WHERE id = ?",
            (int(is_favorite), station_id),
        )
        self.con.commit()

    def is_favorite_station(self, station_id: int) -> bool:
        row = self.con.execute(
            "SELECT is_favorite FROM stations WHERE id = ?", (station_id,)
        ).fetchone()
        return bool(row["is_favorite"]) if row else False

    def list_favorite_stations(self) -> List[Station]:
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.is_favorite = 1
            ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE
            """
        ).fetchall()
        return [
            Station(
                id=r["id"],
                name=r["name"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
                last_played_at=r["last_played_at"],
                is_favorite=True,
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),
                prerolls=self.list_prerolls(r["id"]),                 # Phase 83 D-01/D-03
                prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
                channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
                provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
                live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
                live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
            )
            for r in rows
        ]

    def update_station_art(self, station_id: int, art_path: str) -> None:
        self.con.execute(
            "UPDATE stations SET station_art_path = ? WHERE id = ?",
            (art_path, station_id),
        )
        self.con.commit()

    def update_channel_avatar_path(self, station_id: int, path: Optional[str]) -> None:
        """Phase 89 D-13: write channel_avatar_path for station.

        Not routed through update_station to avoid silent-reset of avatar on saves
        that don't touch the avatar column (RESEARCH.md Pitfall 5).
        Superseded by update_provider_avatar_path as of Phase 89.1 — no new callers
        should be added here (D-04, write-path cutover to providers table).
        """
        self.con.execute(
            "UPDATE stations SET channel_avatar_path = ? WHERE id = ?",
            (path, station_id),
        )
        self.con.commit()

    def update_provider_avatar_path(self, provider_id: int, path: Optional[str]) -> None:
        """Phase 89.1 D-09: write avatar_path for provider.

        Not routed through a broad provider update to avoid silent-reset of avatar
        on saves that don't touch the avatar column (same Pitfall 5 rationale as
        update_channel_avatar_path). Dedicated single-column UPDATE only.
        """
        self.con.execute(
            "UPDATE providers SET avatar_path = ? WHERE id = ?",
            (path, provider_id),
        )
        self.con.commit()

    def set_live_url_syncs_from_channel(self, station_id: int, value: bool) -> None:
        """Phase 96 D-01: set per-station live URL re-sync flag.

        Not routed through update_station — that method does not include this
        column (Pitfall 1: adding new columns to update_station risks silent-reset
        on saves that omit the kwarg). Dedicated single-column UPDATE only.
        Stores as INTEGER (0/1); callers receive bool via Station dataclass.
        """
        self.con.execute(
            "UPDATE stations SET live_url_syncs_from_channel = ? WHERE id = ?",
            (int(value), station_id),
        )
        self.con.commit()

    def set_live_url_title_anchor(self, station_id: int, title: Optional[str]) -> None:
        """Phase 96 D-03: write/clear the live URL title anchor.

        Not routed through update_station for the same Pitfall 1 reason as
        set_live_url_syncs_from_channel. NULL clears the anchor.
        Security T-96-03: caps title at 500 chars before persist to guard against
        oversized/malicious titles from yt-dlp scan results.
        Parameterized SQL prevents injection (same idiom as all other Repo setters).
        """
        if title is not None:
            title = title[:500]
        self.con.execute(
            "UPDATE stations SET live_url_title_anchor = ? WHERE id = ?",
            (title, station_id),
        )
        self.con.commit()

    def set_provider_channel_scan_url(self, provider_id: int, url: Optional[str]) -> None:
        """Phase 96 D-04: write the channel scan URL for a provider.

        Not routed through a broad provider update to avoid silent-reset of other
        columns (same Pitfall 5 rationale as update_provider_avatar_path).
        Dedicated single-column UPDATE only. NULL clears the scan URL.
        """
        self.con.execute(
            "UPDATE providers SET channel_scan_url = ? WHERE id = ?",
            (url, provider_id),
        )
        self.con.commit()

    def list_flagged_stations_for_provider(self, provider_id: int) -> List[Station]:
        """Phase 96 D-06: stations for this provider where live_url_syncs_from_channel=1.

        Mirrors list_recently_played's Station-building loop but scoped to a single
        provider and the live-sync flag. Used by LiveRefreshDialog (Plan 04) to find
        which stations need their live URL checked against the channel.
        ORDER BY s.name COLLATE NOCASE for deterministic display ordering.
        """
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.provider_id = ?
              AND s.live_url_syncs_from_channel = 1
            ORDER BY s.name COLLATE NOCASE
            """,
            (provider_id,),
        ).fetchall()
        return [
            Station(
                id=r["id"],
                name=r["name"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
                last_played_at=r["last_played_at"],
                is_favorite=bool(r["is_favorite"]),
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),
                prerolls=self.list_prerolls(r["id"]),                 # Phase 83 D-01/D-03
                prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
                channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
                provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
                live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
                live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
            )
            for r in rows
        ]

    def list_stations_for_provider(self, provider_id: int) -> List[Station]:
        """Phase 96.2 D-01: all stations for this provider, flag-independent.

        Copy of list_flagged_stations_for_provider with the
        live_url_syncs_from_channel predicate removed. Used as the merge-target
        dropdown source for newly-discovered rows. ORDER BY s.name COLLATE NOCASE
        satisfies D-04.
        """
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.provider_id = ?
            ORDER BY s.name COLLATE NOCASE
            """,
            (provider_id,),
        ).fetchall()
        return [
            Station(
                id=r["id"],
                name=r["name"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
                last_played_at=r["last_played_at"],
                is_favorite=bool(r["is_favorite"]),
                preferred_stream_id=r["preferred_stream_id"],
                streams=self.list_streams(r["id"]),
                prerolls=self.list_prerolls(r["id"]),                 # Phase 83 D-01/D-03
                prerolls_fetched_at=r["prerolls_fetched_at"],          # Phase 83 D-04
                channel_avatar_path=r["channel_avatar_path"],          # Phase 89 D-13 — deprecated Phase 89.1
                provider_avatar_path=r["provider_avatar_path"],        # Phase 89.1 D-11
                live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96 D-01
                live_url_title_anchor=r["live_url_title_anchor"],      # Phase 96 D-03
            )
            for r in rows
        ]
