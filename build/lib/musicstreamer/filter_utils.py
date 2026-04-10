import re
from musicstreamer.models import Station


def normalize_tags(raw: str) -> list[str]:
    """Split raw tag string on comma/bullet, strip whitespace, deduplicate case-insensitively.

    Preserves first-seen display form for each unique tag (case-folded key).
    """
    tokens = re.split(r"[,\u2022]", raw)
    seen: dict[str, str] = {}
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        key = token.casefold()
        if key not in seen:
            seen[key] = token
    return list(seen.values())


def matches_filter(
    station: Station,
    search_text: str,
    provider_filter: str | None,
    tag_filter: str | None,
) -> bool:
    """Return True if station matches all active filters (AND logic).

    A filter is inactive when its value is empty string or None.
    search_text: case-insensitive substring match against station.name.
    provider_filter: exact match against station.provider_name.
    tag_filter: case-insensitive membership in station's normalized tags.
    """
    if search_text:
        if search_text.casefold() not in station.name.casefold():
            return False

    if provider_filter:
        if station.provider_name != provider_filter:
            return False

    if tag_filter:
        tag_set = {t.casefold() for t in normalize_tags(station.tags)}
        if tag_filter.casefold() not in tag_set:
            return False

    return True


def matches_filter_multi(
    station: Station,
    search_text: str,
    provider_set: set[str],
    tag_set: set[str],
) -> bool:
    """Return True if station matches all active multi-select filters (AND logic between dimensions).

    Within each dimension, OR logic applies:
    - provider_set: station matches if its provider_name is in provider_set
    - tag_set: station matches if any of its tags appear in tag_set (case-insensitive)

    A dimension is inactive when its set is empty.
    search_text: case-insensitive substring match against station.name (inactive when empty).
    """
    if search_text:
        if search_text.casefold() not in station.name.casefold():
            return False

    if provider_set:
        if station.provider_name not in provider_set:
            return False

    if tag_set:
        station_tags = {t.casefold() for t in normalize_tags(station.tags)}
        filter_tags = {t.casefold() for t in tag_set}
        if not station_tags & filter_tags:
            return False

    return True
