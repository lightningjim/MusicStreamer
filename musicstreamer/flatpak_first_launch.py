"""Flatpak first-launch import-wizard detection and offer-once flag logic.

This module is **pure**: importing it does NOT create directories, write files,
or import Qt. Detection logic returns booleans; the Qt wizard (flatpak_import_wizard)
calls these helpers. Mirrors the musicstreamer.paths design intent.

Constants:
    _FLATPAK_INFO   — canonical Flatpak runtime marker (``/.flatpak-info``).
                      Module-level so tests can monkeypatch it exactly as they
                      monkeypatch ``_HOST_DB``.  Production default is
                      ``/.flatpak-info`` which the Flatpak runtime creates for
                      every sandboxed process.  This is the SINGLE source of
                      truth for sandbox detection consumed by both
                      ``migration.run_migration()`` and the wizard-offer gate in
                      ``__main__._run_gui``.
    _HOST_DATA_DIR  — literal host path accessible via the narrow :ro finish-arg
                      mount (D-01).  Must NOT use paths.data_dir() here — inside
                      the Flatpak sandbox XDG_DATA_HOME is remapped to
                      ~/.var/app/…/data so paths.data_dir() returns the *sandbox*
                      path, not the host path (RESEARCH.md Pitfall 7).
    _HOST_DB        — the specific SQLite file we probe for unsandboxed data.

Public API:
    is_sandboxed()               — True iff /.flatpak-info exists (Flatpak runtime marker).
    has_unsandboxed_data()       — True iff _HOST_DB exists as a file.
    import_offered_flag_path()   — path in sandbox data dir for the offer-once flag.
    should_offer_import_wizard() — True iff data exists AND wizard hasn't been offered.
    write_offered_flag()         — creates the flag file (call on dismiss/complete).
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Sandbox-detection constant
# ---------------------------------------------------------------------------

# Canonical Flatpak runtime marker.  The Flatpak runtime creates this file for
# every sandboxed process; it does NOT exist on a native (non-Flatpak) system.
# Module-level so tests can monkeypatch it exactly as they monkeypatch _HOST_DB.
# This is the SINGLE source of truth for sandbox detection — consumed by both
# migration.run_migration() (Phase 86.1 Plan 01) and the wizard-offer gate in
# __main__._run_gui (Phase 86.1 Plan 02).
_FLATPAK_INFO: str = "/.flatpak-info"

# ---------------------------------------------------------------------------
# Literal host path constants
# ---------------------------------------------------------------------------

# The narrow :ro finish-arg mount (D-01) makes ~/.local/share/musicstreamer/
# readable at its HOST path inside the Flatpak sandbox.  We probe this path
# directly — never routed through paths.data_dir() which would return the
# sandbox-remapped path under ~/.var/app/… (RESEARCH.md Pitfall 7).
_HOST_DATA_DIR: str = os.path.expanduser("~/.local/share/musicstreamer")
_HOST_DB: str = os.path.join(_HOST_DATA_DIR, "musicstreamer.sqlite3")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def is_sandboxed() -> bool:
    """Return True iff the process is running inside a Flatpak sandbox.

    Uses the presence of ``/.flatpak-info`` (``_FLATPAK_INFO``) as the single
    source of truth — the Flatpak runtime creates this file for every sandboxed
    process and it does not exist on a native system.

    The constant is module-level so tests can monkeypatch it to a tmp file or
    a non-existent path, mirroring the ``_HOST_DB`` monkeypatch pattern.

    This is the SINGLE source of truth for sandbox detection consumed by:
      - ``migration.run_migration()``  — skips auto-copy when sandboxed
      - ``__main__._run_gui``          — wizard-offer gate (Plan 02)
    """
    return os.path.exists(_FLATPAK_INFO)


def has_unsandboxed_data() -> bool:
    """Return True if old unsandboxed data exists at the narrow :ro mount.

    Probes the LITERAL host path _HOST_DB (not paths.db_path() which remaps
    inside the sandbox).  Safe to call at any point — no side effects.
    """
    return os.path.isfile(_HOST_DB)


def import_offered_flag_path() -> str:
    """Return the path of the offer-once flag file inside the sandbox data dir.

    The flag lives in the *sandbox* data dir (paths.data_dir()), not on the
    host.  Its presence means the wizard has been offered at least once.

    Uses paths.data_dir() here (not _HOST_DATA_DIR) because this is the correct
    location for sandbox-writable state — the only use of paths.data_dir() in
    this module.
    """
    from musicstreamer import paths  # late import keeps module Qt-free at import time

    return os.path.join(paths.data_dir(), ".flatpak-import-offered")


def should_offer_import_wizard() -> bool:
    """Return True iff the import wizard should be shown to the user.

    Returns True only when:
      1. Unsandboxed host data exists (has_unsandboxed_data()), AND
      2. The offer-once flag is absent (wizard hasn't been offered before, D-03).

    Returns False in all other cases, including:
      - No host DB present (fresh Flatpak install with no prior unsandboxed data)
      - Offer flag exists (wizard already dismissed/completed once)
    """
    if not has_unsandboxed_data():
        return False
    return not os.path.isfile(import_offered_flag_path())


# ---------------------------------------------------------------------------
# Flag write (called by wizard on dismiss or successful completion)
# ---------------------------------------------------------------------------


def write_offered_flag() -> None:
    """Create the offer-once flag file in the sandbox data dir (D-03).

    Called by FlatpakImportWizard on both dismiss and successful import
    completion so the wizard is never offered again in the same sandbox.

    Idempotent: calling more than once is safe and has no effect if the
    flag already exists.
    """
    flag_path = import_offered_flag_path()
    flag_dir = os.path.dirname(flag_path)
    os.makedirs(flag_dir, exist_ok=True)
    # Open in "a" (append) mode so the call is idempotent; creates the file
    # if absent, leaves existing content untouched if present.
    open(flag_path, "a").close()
