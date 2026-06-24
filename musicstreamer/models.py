from dataclasses import dataclass, field
from typing import Optional, List, Literal


@dataclass
class Provider:
    id: int
    name: str
    channel_scan_url: Optional[str] = None      # Phase 96 D-04


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
    cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"  # Phase 73 D-01/D-05
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False
    preferred_stream_id: Optional[int] = None  # Phase 82 D-01: per-station sticky preferred stream
    canonical_stream_id: Optional[int] = None  # Phase 97 D-04: metadata anchor stream (separate from playback preferred)
    prerolls: List[str] = field(default_factory=list)              # Phase 83 D-01/D-03
    prerolls_fetched_at: Optional[int] = None                      # Phase 83 D-04
    channel_avatar_path: Optional[str] = None                      # Phase 89 D-13 — deprecated Phase 89.1 (use provider_avatar_path)
    provider_avatar_path: Optional[str] = None                     # Phase 89.1 D-11
    live_url_syncs_from_channel: bool = False                      # Phase 96 D-01
    live_url_title_anchor: Optional[str] = None                    # Phase 96 D-03

    @property
    def canonical_url(self) -> str:
        """Phase 97 D-07: URL of the canonical (metadata anchor) stream.

        Resolution order (D-05: playback preferred_stream_id is untouched):
          1. Stream matching canonical_stream_id (if set and present)
          2. Position-1 stream (fallback: canonical_stream_id unset or stale FK after delete)
          3. "" (no streams at all)
        """
        if not self.streams:
            return ""
        if self.canonical_stream_id is not None:
            for s in self.streams:
                if s.id == self.canonical_stream_id:
                    return s.url
        by_pos = sorted(self.streams, key=lambda s: (s.position, s.id))
        return by_pos[0].url if by_pos else ""


@dataclass
class Favorite:
    id: int
    station_name: str
    provider_name: str
    track_title: str
    genre: str
    created_at: Optional[str] = None
