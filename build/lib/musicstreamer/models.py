from dataclasses import dataclass
from typing import Optional


@dataclass
class Provider:
    id: int
    name: str


@dataclass
class Station:
    id: int
    name: str
    url: str
    provider_id: Optional[int]
    provider_name: Optional[str]
    tags: str
    station_art_path: Optional[str]
    album_fallback_path: Optional[str]
    icy_disabled: bool = False
    last_played_at: Optional[str] = None


@dataclass
class Favorite:
    id: int
    station_name: str
    provider_name: str
    track_title: str
    genre: str
    created_at: Optional[str] = None
