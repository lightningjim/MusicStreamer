"""Pure playlist parser for PLS, M3U/M3U8, and XSPF formats (Phase 58 / D-09).

parse_playlist(body, content_type, url_hint) -> list[dict]

Each dict has exactly four keys: url, title, bitrate_kbps, codec.
No Qt dependency. No I/O — caller provides the body. File-order preserved
(gap-06 invariant promoted from aa_import._resolve_pls).

Format dispatch (D-19): URL extension first, Content-Type second, give up
third. No body sniffing.

Phase title stays 'PLS Auto-Resolve' (D-18); the M3U/M3U8/XSPF support
is an internal capability — same module, multiple private dispatchers.
"""
from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Module-level constants (D-11)
# ---------------------------------------------------------------------------

_BITRATE_RE = re.compile(r"(\d+)\s*k(?:b(?:ps)?)?\b", re.IGNORECASE)

# Priority order matters: HE-AAC scanned before AAC+ before AAC so that
# "DI.fm HE-AAC 64kbps" returns "HE-AAC", not the substring "AAC".
# Known acceptable gaps (RESEARCH Findings 3, 4, 5):
#   - "HEAACv2" matches "AAC" (same codec family for ordering — safe)
#   - "VORBIS", "M4A", "ALAC" return "" (not in v1 token list per D-11)
_CODEC_TOKENS = ["HE-AAC", "AAC+", "AAC", "OGG", "FLAC", "OPUS", "MP3", "WMA"]

_XSPF_NS = "http://xspf.org/ns/0/"


# ---------------------------------------------------------------------------
# Public API (D-09)
# ---------------------------------------------------------------------------

def parse_playlist(
    body: str | bytes,
    content_type: str = "",
    url_hint: str = "",
) -> list[dict]:
    """Dispatch to PLS/M3U/M3U8/XSPF parser by URL extension then Content-Type.

    Returns list of {url, title, bitrate_kbps, codec} dicts in playlist
    file order. Returns [] when format is unrecognized or body is malformed
    (not an error — caller decides what to surface).

    Format dispatch (D-19):
      1. URL extension (.pls, .m3u, .m3u8, .xspf) — cheapest, no I/O
      2. Content-Type response header — fallback when extension unknown
      3. give up — return []

    body accepts both str and bytes (D-17). XSPF always uses raw bytes
    internally so ElementTree honors the XML prologue's encoding declaration;
    PLS/M3U/M3U8 decode bytes with errors="replace".
    """
    # 1. URL extension dispatch (strip query string before extension check)
    path = urllib.parse.urlparse(url_hint).path.lower()
    ext = os.path.splitext(path)[1]

    if ext == ".pls":
        return _parse_pls(_as_text(body))
    if ext in (".m3u", ".m3u8"):
        return _parse_m3u(_as_text(body))
    if ext == ".xspf":
        return _parse_xspf(_as_bytes(body))

    # 2. Content-Type fallback (substring match — handles "audio/x-scpls; charset=utf-8")
    ct = content_type.lower()
    if "scpls" in ct:
        return _parse_pls(_as_text(body))
    if "mpegurl" in ct or "apple.mpegurl" in ct:
        return _parse_m3u(_as_text(body))
    if "xspf" in ct:
        return _parse_xspf(_as_bytes(body))

    # 3. Give up
    return []


# ---------------------------------------------------------------------------
# Bytes / str helpers (D-17)
# ---------------------------------------------------------------------------

def _as_text(body: str | bytes) -> str:
    """Return body as a str, decoding bytes with errors='replace' if necessary."""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return body


def _as_bytes(body: str | bytes) -> bytes:
    """Return body as bytes, encoding str as UTF-8 if necessary."""
    if isinstance(body, str):
        return body.encode("utf-8")
    return body


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

def _parse_pls(body: str) -> list[dict]:
    """Parse a PLS body. Per D-11 + gap-06 file-order preservation.

    Returns one dict per FileN= entry sorted by numeric N (gap-06 invariant
    promoted from aa_import._resolve_pls). TitleN is optional; missing title
    yields empty string (D-14/D-15).
    """
    url_dict: dict[int, str] = {}
    title_dict: dict[int, str] = {}
    for raw_line in body.splitlines():
        # BOM safety: U+FEFF can appear at file start in latin-1/Win-1252
        # PLS files; strip on every line to be permissive.
        line = raw_line.lstrip("﻿").strip()
        if not line:
            continue
        m = re.match(r"^File(\d+)=(.+)$", line, re.IGNORECASE)
        if m:
            url_dict[int(m.group(1))] = m.group(2).strip()
            continue
        m = re.match(r"^Title(\d+)=(.+)$", line, re.IGNORECASE)
        if m:
            title_dict[int(m.group(1))] = m.group(2).strip()

    result: list[dict] = []
    for idx in sorted(url_dict):  # numeric file-order (gap-06)
        title = title_dict.get(idx, "")
        result.append({
            "url": url_dict[idx],
            "title": title,
            "bitrate_kbps": _extract_bitrate(title),
            "codec": _extract_codec(title),
        })
    return result


def _parse_m3u(body: str) -> list[dict]:
    """Parse an M3U / M3U8 body. Per D-12 — #EXT-X-STREAM-INF deferred.

    Pairs each #EXTINF display name with the next URL line. URL lines with
    no preceding #EXTINF yield title="" (D-12). #EXT-X-STREAM-INF master
    playlist attributes are NOT parsed in v1 per D-12.
    """
    result: list[dict] = []
    prev_extinf: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.lstrip("﻿").strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            # Form is `#EXTINF:DURATION[ attr="v"...],DISPLAY_NAME`
            # Display name starts after the FIRST comma.
            comma = line.find(",")
            prev_extinf = line[comma + 1:].strip() if comma != -1 else ""
            continue
        if line.startswith("#"):
            # Other directive (#EXT-X-*, comment) — do NOT clear prev_extinf
            continue
        # URL line: pair with prev_extinf (or empty if none)
        title = prev_extinf or ""
        result.append({
            "url": line,
            "title": title,
            "bitrate_kbps": _extract_bitrate(title),
            "codec": _extract_codec(title),
        })
        prev_extinf = None
    return result


def _parse_xspf(body: bytes) -> list[dict]:
    """Parse an XSPF body. Per D-13 — plain ET.fromstring, no defusedxml.

    The user pastes their own URL into their own dialog; nothing crosses a
    peer-trust boundary. expat blocks XXE (SYSTEM entities) by default.
    Internal entity expansion is bounded by the user-pasted threat model.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    result: list[dict] = []
    for track in root.findall(f".//{{{_XSPF_NS}}}track"):
        loc_el = track.find(f"{{{_XSPF_NS}}}location")
        if loc_el is None or not loc_el.text:
            continue
        title_el = track.find(f"{{{_XSPF_NS}}}title")
        title = (title_el.text or "") if title_el is not None else ""
        url = loc_el.text.strip()
        result.append({
            "url": url,
            "title": title,
            "bitrate_kbps": _extract_bitrate(title),
            "codec": _extract_codec(title),
        })
    return result


# ---------------------------------------------------------------------------
# Bitrate / codec extractors (D-11 / D-15)
# ---------------------------------------------------------------------------

def _extract_bitrate(title: str) -> int:
    """Return bitrate in kbps from a title string, or 0 if no match.

    D-11 regex: (\\d+)\\s*k(?:b(?:ps)?)?\\b case-insensitive.
    Known minor over-match accepted: "Some 2k station" -> 2 (RESEARCH Finding 1).
    D-16: callers render bitrate_kbps=0 as empty string downstream.
    """
    m = _BITRATE_RE.search(title)
    return int(m.group(1)) if m else 0


def _extract_codec(title: str) -> str:
    """Return canonical codec token from a title string, or '' if no match (D-15).

    Priority order matters — HE-AAC before AAC+ before AAC so that
    "HE-AAC 64k" returns "HE-AAC", not the substring "AAC".
    D-15: blank ('') is the correct sentinel — never 'unknown', never None.
    """
    upper = title.upper()
    for token in _CODEC_TOKENS:
        if token in upper:
            return token
    return ""
