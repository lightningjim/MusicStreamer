import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite
from musicstreamer.constants import DB_PATH


def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
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
          url TEXT NOT NULL,
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
        con.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # table already exists


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
                    url=r["url"],
                    provider_id=r["provider_id"],
                    provider_name=r["provider_name"],
                    tags=r["tags"] or "",
                    station_art_path=r["station_art_path"],
                    album_fallback_path=r["album_fallback_path"],
                    icy_disabled=bool(r["icy_disabled"]),
                    last_played_at=r["last_played_at"],
                )
            )
        return out

    def create_station(self) -> int:
        cur = self.con.execute(
            "INSERT INTO stations(name, url) VALUES ('New Station', '')"
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
            url=r["url"],
            provider_id=r["provider_id"],
            provider_name=r["provider_name"],
            tags=r["tags"] or "",
            station_art_path=r["station_art_path"],
            album_fallback_path=r["album_fallback_path"],
            icy_disabled=bool(r["icy_disabled"]),
            last_played_at=r["last_played_at"],
        )

    def delete_station(self, station_id: int):
        self.con.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        self.con.commit()

    def update_station(
        self,
        station_id: int,
        name: str,
        url: str,
        provider_id: Optional[int],
        tags: str,
        station_art_path: Optional[str],
        album_fallback_path: Optional[str],
        icy_disabled: bool = False,
    ):
        self.con.execute(
            """
            UPDATE stations
            SET name = ?, url = ?, provider_id = ?, tags = ?,
                station_art_path = ?, album_fallback_path = ?, icy_disabled = ?
            WHERE id = ?
            """,
            (name, url, provider_id, tags, station_art_path, album_fallback_path,
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
                url=r["url"],
                provider_id=r["provider_id"],
                provider_name=r["provider_name"],
                tags=r["tags"] or "",
                station_art_path=r["station_art_path"],
                album_fallback_path=r["album_fallback_path"],
                icy_disabled=bool(r["icy_disabled"]),
                last_played_at=r["last_played_at"],
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
            "SELECT 1 FROM stations WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int:
        provider_id = self.ensure_provider(provider_name) if provider_name else None
        cur = self.con.execute(
            "INSERT INTO stations(name, url, provider_id, tags) VALUES (?, ?, ?, ?)",
            (name, url, provider_id, tags or ""),
        )
        self.con.commit()
        return int(cur.lastrowid)
