"""Tests for musicstreamer.flatpak_first_launch detection + offer-once logic.

Covers (per 86-02-PLAN.md Task 1 <behavior>):
  - has_unsandboxed_data() returns True iff the literal _HOST_DB file exists
  - import_offered_flag_path() returns a path inside paths.data_dir()
  - should_offer_import_wizard() returns True iff host DB exists AND no flag
  - should_offer_import_wizard() returns False when offer flag exists (offer-once, D-03)
  - should_offer_import_wizard() returns False when no host DB exists
"""
from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_flag(flag_path: str) -> None:
    """Create the offer-once flag file (simulating wizard dismiss/complete)."""
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    open(flag_path, "w").close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHasUnsandboxedData:
    """has_unsandboxed_data() probes the _HOST_DB literal path."""

    def test_returns_true_when_host_db_exists(self, tmp_path, monkeypatch):
        """Returns True when the monkeypatched _HOST_DB file exists."""
        import musicstreamer.flatpak_first_launch as ffl

        db_file = tmp_path / "musicstreamer.sqlite3"
        db_file.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(db_file))

        assert ffl.has_unsandboxed_data() is True

    def test_returns_false_when_host_db_missing(self, tmp_path, monkeypatch):
        """Returns False when no DB file is at the host path."""
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(ffl, "_HOST_DB", str(tmp_path / "does_not_exist.sqlite3"))

        assert ffl.has_unsandboxed_data() is False

    def test_returns_false_when_host_db_is_directory(self, tmp_path, monkeypatch):
        """Returns False if the path exists but is a directory, not a file."""
        import musicstreamer.flatpak_first_launch as ffl

        dir_path = tmp_path / "musicstreamer.sqlite3"
        dir_path.mkdir()
        monkeypatch.setattr(ffl, "_HOST_DB", str(dir_path))

        assert ffl.has_unsandboxed_data() is False


class TestImportOfferedFlagPath:
    """import_offered_flag_path() returns a path inside paths.data_dir()."""

    def test_returns_path_inside_data_dir(self, tmp_path, monkeypatch):
        """Flag path is rooted at paths.data_dir() (the sandbox dir)."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))

        flag = ffl.import_offered_flag_path()
        assert flag.startswith(str(tmp_path)), (
            f"Flag path {flag!r} should be inside data_dir {tmp_path}"
        )

    def test_flag_filename_ends_with_flatpak_import_offered(self, tmp_path, monkeypatch):
        """Flag filename ends with .flatpak-import-offered."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))

        flag = ffl.import_offered_flag_path()
        assert os.path.basename(flag) == ".flatpak-import-offered"


class TestShouldOfferImportWizard:
    """should_offer_import_wizard() combines DB presence + offer-once flag."""

    def test_returns_true_when_db_exists_and_no_flag(self, tmp_path, monkeypatch):
        """Returns True on first launch with existing host DB, no flag."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        db_file = tmp_path / "host_db" / "musicstreamer.sqlite3"
        db_file.parent.mkdir()
        db_file.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(db_file))
        # Use a separate dir for sandbox data dir (no flag created)
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        assert ffl.should_offer_import_wizard() is True

    def test_returns_false_when_offer_flag_exists(self, tmp_path, monkeypatch):
        """Returns False (offer-once D-03) when flag file already exists."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        db_file = tmp_path / "host_db" / "musicstreamer.sqlite3"
        db_file.parent.mkdir()
        db_file.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(db_file))

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        # Write the offer flag
        flag_path = ffl.import_offered_flag_path()
        _write_flag(flag_path)

        assert ffl.should_offer_import_wizard() is False

    def test_returns_false_when_no_host_db(self, tmp_path, monkeypatch):
        """Returns False when no pre-existing host data dir (fresh Flatpak user)."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(
            ffl, "_HOST_DB", str(tmp_path / "no_host_db" / "musicstreamer.sqlite3")
        )

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        assert ffl.should_offer_import_wizard() is False

    def test_returns_false_after_write_offered_flag_called(self, tmp_path, monkeypatch):
        """Returns False after write_offered_flag() is called (offer-once write path)."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        db_file = tmp_path / "host_db" / "musicstreamer.sqlite3"
        db_file.parent.mkdir()
        db_file.write_bytes(b"")
        monkeypatch.setattr(ffl, "_HOST_DB", str(db_file))

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        monkeypatch.setattr(paths_mod, "_root_override", str(sandbox_dir))

        # Precondition: wizard would be offered before writing flag
        assert ffl.should_offer_import_wizard() is True

        # Write flag (simulating wizard dismiss/complete)
        ffl.write_offered_flag()

        # Now should NOT offer again
        assert ffl.should_offer_import_wizard() is False


class TestWriteOfferedFlag:
    """write_offered_flag() creates the offer-once flag file."""

    def test_creates_flag_file(self, tmp_path, monkeypatch):
        """write_offered_flag() creates the flag file in the sandbox data dir."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))

        flag_path = ffl.import_offered_flag_path()
        assert not os.path.exists(flag_path), "flag should not exist before write"

        ffl.write_offered_flag()

        assert os.path.isfile(flag_path), "flag should exist after write_offered_flag()"

    def test_idempotent_second_call(self, tmp_path, monkeypatch):
        """Calling write_offered_flag() twice does not raise."""
        import musicstreamer.paths as paths_mod
        import musicstreamer.flatpak_first_launch as ffl

        monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))

        ffl.write_offered_flag()
        ffl.write_offered_flag()  # should not raise
