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
