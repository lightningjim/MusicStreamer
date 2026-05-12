from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Provider:
    id: int
    name: str


@dataclass
class StationStream:
    id: int
    station_id: int
    url: str
    label: str = ""
    quality: str = ""        # "hi" | "med" | "low" | custom string
    position: int = 1
    stream_type: str = ""    # "shoutcast" | "youtube" | "hls" | ""
    codec: str = ""          # "MP3" | "AAC" | "OPUS" | "FLAC" | ""
    bitrate_kbps: int = 0     # numeric bitrate in kbps; 0 = unknown (D-01)
    sample_rate_hz: int = 0   # Phase 70 — 0 = unknown until first caps detection (DS-05)
    bit_depth: int = 0        # Phase 70 — 0 = unknown until first caps detection (DS-05)


@dataclass
class Station:
    id: int
    name: str
    provider_id: Optional[int]
    provider_name: Optional[str]
    tags: str
    station_art_path: Optional[str]
    album_fallback_path: Optional[str]
    icy_disabled: bool = False
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False


@dataclass
class Favorite:
    id: int
    station_name: str
    provider_name: str
    track_title: str
    genre: str
    created_at: Optional[str] = None
