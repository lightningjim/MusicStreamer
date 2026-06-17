"""Phase 89c ART-AVATAR-11: Provider brand-avatar registry.

Maps the 7 exact provider_name strings (SomaFM + 6 AudioAddict networks) to
bundled PNG filenames. Per D-01, only the registered providers are included.

lookup(provider_name) -> Optional[str]:
  Returns the absolute filesystem path to the bundled PNG only if:
  - The provider_name key is present in _REGISTRY, AND
  - os.path.isfile() confirms the asset is present on disk (D-04 graceful
    missing-asset guard — PNGs arrive from user later per D-04; absent PNG
    === current station-logo behavior, a fully tested path).
  Returns None in all other cases. Never raises (mirrors the
  yt_import.get_avatar_fetcher never-raise contract).
"""
import importlib.resources as _res
import os
from typing import Optional

# Static registry: exact provider_name strings → PNG filename (D-02, D-09a).
# One key per network (7 distinct keys — no shared AudioAddict mark).
# Unregistered providers (not in this dict) return None from lookup().
_REGISTRY: dict[str, str] = {
    "SomaFM":         "SomaFM.png",          # soma_import.py:306
    "DI.fm":          "DI.fm.png",            # aa_import.py:106
    "RadioTunes":     "RadioTunes.png",       # aa_import.py:107
    "JazzRadio":      "JazzRadio.png",        # aa_import.py:108
    "RockRadio":      "RockRadio.png",        # aa_import.py:109
    "ClassicalRadio": "ClassicalRadio.png",   # aa_import.py:110
    "ZenRadio":       "ZenRadio.png",         # aa_import.py:111
}


def lookup(provider_name: str) -> Optional[str]:
    """Return absolute path to bundled brand PNG if registered AND present on disk.

    Phase 89c D-04: if the PNG file is absent (user hasn't supplied it yet),
    returns None — graceful missing-asset, preserves current station-logo
    behavior without crashing.

    Never raises for any string input.
    """
    filename = _REGISTRY.get(provider_name)
    if filename is None:
        return None
    try:
        pkg_path = _res.files("musicstreamer.ui_qt") / "brand-avatars" / filename
        abs_str = str(pkg_path)
    except Exception:  # noqa: BLE001 — never raise (D-04 Pitfall 4)
        return None
    if not os.path.isfile(abs_str):
        return None
    return abs_str
