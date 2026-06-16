import os
import shutil
import tempfile

from musicstreamer import paths


def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
    os.makedirs(paths.channel_avatars_dir(), exist_ok=True)


def copy_asset_for_station(station_id: int, source_path: str, kind: str) -> str:
    """
    Copies the chosen image into ``paths.assets_dir()/<station_id>/<kind>.<ext>``.
    Returns relative path under assets/.
    """
    src = source_path
    ext = os.path.splitext(src)[1].lower() or ".png"
    station_dir = os.path.join(paths.assets_dir(), str(station_id))
    os.makedirs(station_dir, exist_ok=True)

    filename = f"{kind}{ext}"
    dst = os.path.join(station_dir, filename)
    shutil.copy2(src, dst)

    rel = os.path.relpath(dst, paths.data_dir())  # e.g. assets/12/station_art.png
    return rel


def write_channel_avatar(station_id: int, data: bytes) -> str:
    """Write avatar PNG bytes atomically to the channel-avatars directory.

    Returns path relative to paths.data_dir(), e.g. 'assets/channel-avatars/12.png'.
    Uses tempfile.mkstemp in the same directory so os.replace is atomic
    (same filesystem — RESEARCH.md A2 / D-12).

    station_id is an int from SQLite — no user-controlled string, no traversal
    risk (T-89-02).
    """
    dst_dir = paths.channel_avatars_dir()
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{station_id}.png")
    fd, tmp = tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return os.path.relpath(dst, paths.data_dir())


def write_provider_avatar(provider_id: int, data: bytes) -> str:
    """Write avatar PNG bytes atomically keyed by provider_id (Phase 89.1 D-10).

    Returns path relative to paths.data_dir(), e.g. 'assets/channel-avatars/7.png'.
    Uses tempfile.mkstemp + os.replace for atomicity (same as write_channel_avatar).
    provider_id is an int from SQLite PK AUTOINCREMENT — no user-controlled string,
    no traversal risk (T-89.1-01).
    """
    dst_dir = paths.channel_avatars_dir()
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{provider_id}.png")
    fd, tmp = tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")
    try:
        os.write(fd, data)
        os.close(fd)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return os.path.relpath(dst, paths.data_dir())
