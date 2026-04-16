"""Pure export/import logic for MusicStreamer settings — no Qt dependency.

Public API:
    build_zip(repo, dest_path)           — write full settings ZIP
    preview_import(zip_path, repo)       — validate + dry-run, returns ImportPreview
    commit_import(preview, repo, mode)   — apply import atomically (merge | replace_all)

Dataclasses:
    ImportDetailRow  — per-station action row
    ImportPreview    — aggregate result from preview_import, passed to commit_import
"""
from __future__ import annotations

import datetime
import json
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

from musicstreamer import paths
from musicstreamer.models import Favorite, Station
from musicstreamer.repo import Repo

# Settings keys excluded from export (credentials / machine-local secrets).
_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ImportDetailRow:
    name: str
    action: str  # "add" | "replace" | "skip" | "error"
    reason: str = ""


@dataclass
class ImportPreview:
    added: int = 0
    replaced: int = 0
    skipped: int = 0
    errors: int = 0
    detail_rows: list = field(default_factory=list)      # List[ImportDetailRow]
    track_favorites: list = field(default_factory=list)  # raw dicts from JSON
    settings: list = field(default_factory=list)          # raw dicts from JSON
    zip_path: str = ""
    stations_data: list = field(default_factory=list)    # raw station dicts for commit


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize(name: str) -> str:
    """Return a filesystem-safe ASCII filename stem from *name* (max 80 chars)."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s.\-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = name[:80]
    return name or "station"


def _station_to_dict(station: Station) -> dict:
    """Serialize a Station (with its streams) to the settings.json schema."""
    return {
        "name": station.name,
        "provider": station.provider_name or "",
        "tags": station.tags or "",
        "icy_disabled": station.icy_disabled,
        "is_favorite": station.is_favorite,
        "last_played_at": station.last_played_at,
        "logo_file": None,  # populated in build_zip when file exists
        "streams": [
            {
                "url": s.url,
                "label": s.label,
                "quality": s.quality,
                "position": s.position,
                "stream_type": s.stream_type,
                "codec": s.codec,
            }
            for s in station.streams
        ],
    }


def _fav_to_dict(fav: Favorite) -> dict:
    return {
        "station_name": fav.station_name,
        "provider_name": fav.provider_name,
        "track_title": fav.track_title,
        "genre": fav.genre,
        "created_at": fav.created_at,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_zip(repo: Repo, dest_path: str) -> None:
    """Write a complete settings archive to *dest_path*.

    The ZIP contains:
        settings.json  — all stations, favorites, settings (credentials excluded)
        logos/         — logo files for stations that have station_art_path
    """
    stations = repo.list_stations()
    favorites = repo.list_favorites()
    settings_rows = [
        {"key": r["key"], "value": r["value"]}
        for r in repo.con.execute("SELECT key, value FROM settings").fetchall()
        if r["key"] not in _EXCLUDED_SETTINGS
    ]

    station_dicts = [_station_to_dict(s) for s in stations]

    # Resolve logo paths and assign logo_file; handle name collisions via _{id}
    seen_logo_names: dict[str, int] = {}  # sanitized_stem -> first station_id
    for station, d in zip(stations, station_dicts):
        art = station.station_art_path
        if not art:
            continue
        abs_path = art if os.path.isabs(art) else os.path.join(paths.data_dir(), art)
        if not os.path.exists(abs_path):
            continue
        ext = os.path.splitext(abs_path)[1]
        stem = _sanitize(station.name)
        if stem in seen_logo_names and seen_logo_names[stem] != station.id:
            stem = f"{stem}_{station.id}"
        else:
            seen_logo_names[stem] = station.id
        d["logo_file"] = f"logos/{stem}{ext}"
        d["_abs_logo_path"] = abs_path  # temporary key, stripped before JSON dump

    payload = {
        "version": 1,
        "exported_at": datetime.datetime.now().isoformat(),
        "stations": [
            {k: v for k, v in d.items() if not k.startswith("_")} for d in station_dicts
        ],
        "track_favorites": [_fav_to_dict(f) for f in favorites],
        "settings": settings_rows,
    }

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("settings.json", json.dumps(payload, indent=2))
        for d in station_dicts:
            abs_logo = d.get("_abs_logo_path")
            logo_file = d.get("logo_file")
            if abs_logo and logo_file:
                zf.write(abs_logo, logo_file)


def preview_import(zip_path: str, repo: Repo) -> ImportPreview:
    """Validate *zip_path* and return an ImportPreview without modifying the DB.

    Raises ValueError for:
        - Not a valid ZIP archive
        - Unsafe path in archive (path traversal)
        - Missing settings.json
        - Unsupported version
    """
    try:
        zf_handle = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile:
        raise ValueError("Not a valid ZIP archive")

    with zf_handle as zf:
        # Security: reject path traversal members
        for member in zf.infolist():
            fname = member.filename
            if fname.startswith("/") or ".." in fname:
                raise ValueError(f"Unsafe path in archive: {fname}")

        if "settings.json" not in zf.namelist():
            raise ValueError("Missing settings.json")

        payload = json.loads(zf.read("settings.json"))

    if payload.get("version") != 1:
        raise ValueError(f"Unsupported version: {payload.get('version')}")

    preview = ImportPreview(
        zip_path=zip_path,
        track_favorites=payload.get("track_favorites", []),
        settings=payload.get("settings", []),
        stations_data=payload.get("stations", []),
    )

    for station in payload.get("stations", []):
        streams = station.get("streams", [])
        matched_url: Optional[str] = None
        for stream in streams:
            url = stream.get("url", "")
            if url and repo.station_exists_by_url(url):
                matched_url = url
                break

        if matched_url is not None:
            preview.replaced += 1
            row = ImportDetailRow(
                name=station.get("name", ""),
                action="replace",
                reason=f"URL match: {matched_url}",
            )
        else:
            preview.added += 1
            row = ImportDetailRow(
                name=station.get("name", ""),
                action="add",
            )
        preview.detail_rows.append(row)

    return preview


def commit_import(preview: ImportPreview, repo: Repo, mode: str) -> None:
    """Apply *preview* to the DB atomically.

    Args:
        preview: Result from preview_import.
        repo:    Repo instance (uses repo.con for direct SQL within one transaction).
        mode:    "merge" or "replace_all".

    The entire operation is wrapped in a single SQLite transaction so any
    error rolls back all changes. Repo high-level methods (insert_station,
    add_favorite, …) each call con.commit() internally, which would break
    the single-transaction guarantee — so we use repo.con.execute() directly.
    """
    with repo.con:
        if mode == "replace_all":
            repo.con.execute("DELETE FROM station_streams")
            repo.con.execute("DELETE FROM stations")
            repo.con.execute("DELETE FROM favorites")
            repo.con.execute("DELETE FROM providers")

        with zipfile.ZipFile(preview.zip_path, "r") as zf:
            zip_names = set(zf.namelist())

            for station_data, detail_row in zip(preview.stations_data, preview.detail_rows):
                action = detail_row.action

                if action == "add" or (action == "replace" and mode == "replace_all"):
                    station_id = _insert_station(repo, station_data)
                elif action == "replace":
                    # Merge mode — find and update existing station
                    station_id = _replace_station(repo, station_data)
                else:
                    continue  # skip / error rows

                # Extract logo if present in ZIP
                logo_file = station_data.get("logo_file")
                if logo_file and logo_file in zip_names and station_id is not None:
                    ext = os.path.splitext(logo_file)[1]
                    art_rel = f"assets/{station_id}/station_art{ext}"
                    art_abs = os.path.join(paths.data_dir(), art_rel)
                    os.makedirs(os.path.dirname(art_abs), exist_ok=True)
                    with zf.open(logo_file) as logo_src:
                        with open(art_abs, "wb") as logo_dst:
                            logo_dst.write(logo_src.read())
                    repo.con.execute(
                        "UPDATE stations SET station_art_path=? WHERE id=?",
                        (art_rel, station_id),
                    )

        # Favorites: INSERT OR IGNORE (union semantics per D-09)
        for fav in preview.track_favorites:
            repo.con.execute(
                "INSERT OR IGNORE INTO favorites"
                "(station_name, provider_name, track_title, genre, created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    fav.get("station_name", ""),
                    fav.get("provider_name", ""),
                    fav.get("track_title", ""),
                    fav.get("genre", ""),
                    fav.get("created_at"),
                ),
            )

        # Settings: INSERT OR REPLACE
        for setting in preview.settings:
            repo.con.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)",
                (setting["key"], setting["value"]),
            )


def _ensure_provider_in_tx(repo: Repo, name: str) -> Optional[int]:
    """Like repo.ensure_provider but does NOT commit (we're inside a transaction)."""
    name = (name or "").strip()
    if not name:
        return None
    repo.con.execute("INSERT OR IGNORE INTO providers(name) VALUES (?)", (name,))
    row = repo.con.execute(
        "SELECT id FROM providers WHERE name = ?", (name,)
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_station(repo: Repo, data: dict) -> int:
    """Insert a new station from import data; returns station_id."""
    provider_id = _ensure_provider_in_tx(repo, data.get("provider", ""))
    cur = repo.con.execute(
        "INSERT INTO stations(name, provider_id, tags, icy_disabled, last_played_at, is_favorite) "
        "VALUES (?,?,?,?,?,?)",
        (
            data.get("name", ""),
            provider_id,
            data.get("tags", ""),
            int(bool(data.get("icy_disabled", False))),
            data.get("last_played_at"),
            int(bool(data.get("is_favorite", False))),
        ),
    )
    station_id = int(cur.lastrowid)

    for stream in data.get("streams", []):
        repo.con.execute(
            "INSERT INTO station_streams"
            "(station_id, url, label, quality, position, stream_type, codec) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                station_id,
                stream.get("url", ""),
                stream.get("label", ""),
                stream.get("quality", ""),
                stream.get("position", 1),
                stream.get("stream_type", ""),
                stream.get("codec", ""),
            ),
        )
    return station_id


def _replace_station(repo: Repo, data: dict) -> Optional[int]:
    """Update existing station matched by stream URL; returns station_id."""
    # Find station_id via matched URL
    station_id: Optional[int] = None
    for stream in data.get("streams", []):
        url = stream.get("url", "")
        if not url:
            continue
        row = repo.con.execute(
            "SELECT station_id FROM station_streams WHERE url=?", (url,)
        ).fetchone()
        if row:
            station_id = int(row["station_id"])
            break

    if station_id is None:
        return None

    provider_id = _ensure_provider_in_tx(repo, data.get("provider", ""))

    # Delete stale streams before re-inserting (Pitfall 2)
    repo.con.execute("DELETE FROM station_streams WHERE station_id=?", (station_id,))

    repo.con.execute(
        "UPDATE stations SET name=?, provider_id=?, tags=?, icy_disabled=?, "
        "last_played_at=?, is_favorite=? WHERE id=?",
        (
            data.get("name", ""),
            provider_id,
            data.get("tags", ""),
            int(bool(data.get("icy_disabled", False))),
            data.get("last_played_at"),
            int(bool(data.get("is_favorite", False))),
            station_id,
        ),
    )

    for stream in data.get("streams", []):
        repo.con.execute(
            "INSERT INTO station_streams"
            "(station_id, url, label, quality, position, stream_type, codec) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                station_id,
                stream.get("url", ""),
                stream.get("label", ""),
                stream.get("quality", ""),
                stream.get("position", 1),
                stream.get("stream_type", ""),
                stream.get("codec", ""),
            ),
        )
    return station_id
