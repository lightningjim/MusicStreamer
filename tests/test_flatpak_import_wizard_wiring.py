"""Tests for the FlatpakImportWizard offer-gate composition used by _run_gui.

Exercises the GATE: ``flatpak_first_launch.is_sandboxed() and
flatpak_first_launch.should_offer_import_wizard()`` — four cases matching
Phase 86.1 Plan 02 Task 2 <behavior>:

1. Sandboxed + host DB present + no flag  → gate True  (offer fires)
2. NOT sandboxed + host DB present        → gate False (no offer on native Linux)
3. Sandboxed + host DB present + flag     → gate False (offer-once holds D-03)
4. Sandboxed + no host DB                 → gate False (fresh Flatpak user)

Qt-free / headless-CI-safe: no PySide6 import, no FlatpakImportWizard
construction.  Monkeypatches the same three module-level constants used by
the existing test suite in test_flatpak_first_launch.py:
  - flatpak_first_launch._FLATPAK_INFO  (sandboxed=True → existing file)
  - flatpak_first_launch._HOST_DB       (host-data-present → existing file)
  - paths._root_override                (sandbox data dir for offer-once flag)
"""
from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Helper: evaluate the composed gate that _run_gui uses
# ---------------------------------------------------------------------------


def _gate(ffl) -> bool:
    """Mirror the gate expression from __main__._maybe_offer_import."""
    return ffl.is_sandboxed() and ffl.should_offer_import_wizard()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWizardOfferGate:
    """Four-case coverage of is_sandboxed() AND should_offer_import_wizard()."""

    def test_sandboxed_with_data_and_no_flag_gate_is_true(
        self, tmp_path, monkeypatch
    ):
        """Case 1: sandboxed + host DB present + no offer flag → gate True (offer fires)."""
        import musicstreamer.flatpak_first_launch as ffl
        import musicstreamer.paths as paths_mod

        # Sandboxed: _FLATPAK_INFO points to an existing file
        info_file = tmp_path / "flatpak-info"
        info_file.write_text("[Application]\nname=io.github.kcreasey.MusicStreamer\n")
        monkeypatch.setattr(ffl, "_FLATPAK_INFO", str(info_file))

        # Host DB present
        host_db = tmp_path / "host" / "musicstreamer.sqlite3"
        host_db.parent.mkdir()
        host_db.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(host_db))

        # Sandbox data dir — offer-once flag NOT created
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        assert _gate(ffl) is True

    def test_not_sandboxed_with_data_gate_is_false(self, tmp_path, monkeypatch):
        """Case 2: NOT sandboxed + host DB present → gate False (no offer on native Linux).

        Even though should_offer_import_wizard() would return True (data present,
        no flag), is_sandboxed() is False so the composed gate is False.
        This proves native Linux never gets the offer.
        """
        import musicstreamer.flatpak_first_launch as ffl
        import musicstreamer.paths as paths_mod

        # NOT sandboxed: _FLATPAK_INFO points to a non-existent path
        monkeypatch.setattr(ffl, "_FLATPAK_INFO", str(tmp_path / "no-flatpak-info"))

        # Host DB present (should_offer alone would be True)
        host_db = tmp_path / "host" / "musicstreamer.sqlite3"
        host_db.parent.mkdir()
        host_db.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(host_db))

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        # Confirm should_offer alone is True to prove the is_sandboxed conjunct gates it
        assert ffl.should_offer_import_wizard() is True
        assert ffl.is_sandboxed() is False
        assert _gate(ffl) is False

    def test_sandboxed_with_data_and_flag_present_gate_is_false(
        self, tmp_path, monkeypatch
    ):
        """Case 3: sandboxed + host DB present + offer-once flag written → gate False.

        Proves offer-once (D-03): after the user dismisses/completes the wizard,
        a relaunch does NOT re-offer.
        """
        import musicstreamer.flatpak_first_launch as ffl
        import musicstreamer.paths as paths_mod

        # Sandboxed
        info_file = tmp_path / "flatpak-info"
        info_file.write_text("[Application]\nname=io.github.kcreasey.MusicStreamer\n")
        monkeypatch.setattr(ffl, "_FLATPAK_INFO", str(info_file))

        # Host DB present
        host_db = tmp_path / "host" / "musicstreamer.sqlite3"
        host_db.parent.mkdir()
        host_db.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(host_db))

        # Sandbox data dir
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        # Simulate wizard dismiss: write the offer-once flag
        ffl.write_offered_flag()
        assert os.path.isfile(ffl.import_offered_flag_path()), "flag must exist"

        assert _gate(ffl) is False

    def test_sandboxed_no_host_db_gate_is_false(self, tmp_path, monkeypatch):
        """Case 4: sandboxed + no host DB → gate False (fresh Flatpak user, nothing to import)."""
        import musicstreamer.flatpak_first_launch as ffl
        import musicstreamer.paths as paths_mod

        # Sandboxed
        info_file = tmp_path / "flatpak-info"
        info_file.write_text("[Application]\nname=io.github.kcreasey.MusicStreamer\n")
        monkeypatch.setattr(ffl, "_FLATPAK_INFO", str(info_file))

        # No host DB
        monkeypatch.setattr(
            ffl, "_HOST_DB", str(tmp_path / "no_host" / "musicstreamer.sqlite3")
        )

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        assert _gate(ffl) is False
