import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite, StationStream
from musicstreamer import paths


def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
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


class Repo:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def list_providers(self) -> List[Provider]:
        rows = self.con.execute("SELECT id, name FROM providers ORDER BY name").fetchall()
        return [Provider(id=r["id"], name=r["name"]) for r in rows]

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
                stream_type=r["stream_type"], codec=r["codec"]) for r in rows]

    def insert_stream(self, station_id: int, url: str, label: str = "",
                      quality: str = "", position: int = 1,
                      stream_type: str = "", codec: str = "") -> int:
        cur = self.con.execute(
            "INSERT INTO station_streams(station_id,url,label,quality,position,stream_type,codec) VALUES(?,?,?,?,?,?,?)",
            (station_id, url, label, quality, position, stream_type, codec))
        self.con.commit()
        return int(cur.lastrowid)

    def update_stream(self, stream_id: int, url: str, label: str,
                      quality: str, position: int, stream_type: str, codec: str):
        self.con.execute(
            "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=? WHERE id=?",
            (url, label, quality, position, stream_type, codec, stream_id))
        self.con.commit()

    def delete_stream(self, stream_id: int):
        self.con.execute("DELETE FROM station_streams WHERE id=?", (stream_id,))
        self.con.commit()

    def reorder_streams(self, station_id: int, ordered_ids: List[int]):
        for pos, sid in enumerate(ordered_ids, 1):
            self.con.execute("UPDATE station_streams SET position=? WHERE id=? AND station_id=?",
                             (pos, sid, station_id))
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
            SELECT s.*, p.name AS provider_name
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            ORDER BY COALESCE(p.name,''), s.name
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
                    last_played_at=r["last_played_at"],
                    is_favorite=bool(r["is_favorite"]),
                    streams=self.list_streams(r["id"]),
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
            SELECT s.*, p.name AS provider_name
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
            last_played_at=r["last_played_at"],
            is_favorite=bool(r["is_favorite"]),
            streams=self.list_streams(station_id),
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
    ):
        self.con.execute(
            """
            UPDATE stations
            SET name = ?, provider_id = ?, tags = ?,
                station_art_path = ?, album_fallback_path = ?, icy_disabled = ?
            WHERE id = ?
            """,
            (name, provider_id, tags, station_art_path, album_fallback_path,
             int(icy_disabled), station_id),
        )
        self.con.commit()

    def update_last_played(self, station_id: int):
        self.con.execute(
            "UPDATE stations SET last_played_at = strftime('%Y-%m-%dT%H:%M:%f', 'now') WHERE id = ?",
            (station_id,),
        )
        self.con.commit()

    def list_recently_played(self, n: int = 3) -> List[Station]:
        rows = self.con.execute(
            """
            SELECT s.*, p.name AS provider_name
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
                last_played_at=r["last_played_at"],
                is_favorite=bool(r["is_favorite"]),
                streams=self.list_streams(r["id"]),
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
            SELECT s.*, p.name AS provider_name
            FROM stations s
            LEFT JOIN providers p ON p.id = s.provider_id
            WHERE s.is_favorite = 1
            ORDER BY COALESCE(p.name,''), s.name
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
                last_played_at=r["last_played_at"],
                is_favorite=True,
                streams=self.list_streams(r["id"]),
            )
            for r in rows
        ]

    def update_station_art(self, station_id: int, art_path: str) -> None:
        self.con.execute(
            "UPDATE stations SET station_art_path = ? WHERE id = ?",
            (art_path, station_id),
        )
        self.con.commit()
