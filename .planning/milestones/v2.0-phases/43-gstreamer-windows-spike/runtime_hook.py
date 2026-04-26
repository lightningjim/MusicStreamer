# Phase 43 spike — custom runtime hook.
# Runs after pyi_rth_gstreamer.py (alphabetical order; hook-contrib rthook prefix is pyi_).
# Sets GIO_EXTRA_MODULES, GI_TYPELIB_PATH, GST_PLUGIN_SCANNER — NOT covered by the stock rthook.
import os
import sys


def _bundle_path(*parts: str) -> str:
    """Resolve a path relative to the onedir bundle root (_internal/ in onedir)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.join(base, *parts)


def _set_if_unset_or_override(key: str, value: str) -> None:
    """Overwrite — bundle paths must win over any ambient env the user might have."""
    os.environ[key] = value


# --- GIO TLS backend ------------------------------------------------------
# libgiognutls.dll lives here; without GIO_EXTRA_MODULES, souphttpsrc fails
# HTTPS with "TLS/SSL support not available; install glib-networking".
# GIO_EXTRA_MODULES is additive to the default search path; use instead of
# GIO_MODULE_DIR (which REPLACES the path and can break other modules).
_set_if_unset_or_override(
    "GIO_EXTRA_MODULES",
    _bundle_path("gio", "modules"),
)

# --- GI typelibs ----------------------------------------------------------
# `gi` hook normally sets this, but the MSVC layout sometimes mislocates the
# dir. Force it explicitly to the bundled copy.
_set_if_unset_or_override(
    "GI_TYPELIB_PATH",
    _bundle_path("girepository-1.0"),
)

# --- Plugin scanner helper binary ----------------------------------------
# playbin3 spawns this to inspect unknown plugins. If unset, GStreamer logs
# "plugin scanner helper not found" and falls back to in-process scanning
# (slower, and can crash on bad plugins).
_scanner = _bundle_path("gst-plugin-scanner.exe")
if os.path.isfile(_scanner):
    _set_if_unset_or_override("GST_PLUGIN_SCANNER", _scanner)

# --- Diagnostics marker --------------------------------------------------
# Printed to stderr so the paste-back shows which env the rthook applied.
# Stable prefix "SPIKE_DIAG_RTHOOK" so the smoke test / build log can grep it.
print(
    f"SPIKE_DIAG_RTHOOK gio_extra_modules={os.environ['GIO_EXTRA_MODULES']!r} "
    f"gi_typelib_path={os.environ['GI_TYPELIB_PATH']!r} "
    f"gst_plugin_scanner={os.environ.get('GST_PLUGIN_SCANNER', '<unset>')!r}",
    file=sys.stderr,
)
