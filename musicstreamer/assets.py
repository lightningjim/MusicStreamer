import os
import shutil

from musicstreamer.constants import DATA_DIR, ASSETS_DIR


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)


def copy_asset_for_station(station_id: int, source_path: str, kind: str) -> str:
    """
    Copies the chosen image into ~/.local/share/musicstreamer/assets/<station_id>/<kind>.<ext>
    Returns relative path under assets/.
    """
    src = source_path
    ext = os.path.splitext(src)[1].lower() or ".png"
    station_dir = os.path.join(ASSETS_DIR, str(station_id))
    os.makedirs(station_dir, exist_ok=True)

    filename = f"{kind}{ext}"
    dst = os.path.join(station_dir, filename)
    shutil.copy2(src, dst)

    rel = os.path.relpath(dst, DATA_DIR)  # e.g. assets/12/station_art.png
    return rel
