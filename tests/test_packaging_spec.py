"""Phase 65 / VER-02-H — PyInstaller spec source-text assertions.

The Windows PyInstaller bundle must ship musicstreamer's dist-info so that
importlib.metadata.version("musicstreamer") resolves inside the bundled exe
(used by both __main__._run_gui's setApplicationVersion call AND the
hamburger menu version footer). Without copy_metadata("musicstreamer"),
the bundle would raise PackageNotFoundError when MainWindow constructs.

These tests are SOURCE-TEXT tests — they read the .spec file as text and
assert substrings are present. They do NOT require PyInstaller to be
installed in the test environment, and they do NOT execute the .spec.

Pattern: mirrors tests/test_main_run_gui_ordering.py's `read_text` +
substring-assertion idiom (PATTERNS §8 — closer analog than
test_pkg03_compliance.py, which is a multi-file glob over musicstreamer/*.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.spec"
)


@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


def test_spec_imports_copy_metadata(spec_source: str) -> None:
    """Phase 65 D-08: spec extends the existing PyInstaller.utils.hooks import
    to include copy_metadata alongside collect_all."""
    assert "copy_metadata" in spec_source, (
        "MusicStreamer.spec must import copy_metadata from "
        "PyInstaller.utils.hooks (alongside collect_all) so musicstreamer's "
        "dist-info ships in the Windows bundle."
    )
    assert (
        "from PyInstaller.utils.hooks import collect_all, copy_metadata"
        in spec_source
        or "from PyInstaller.utils.hooks import copy_metadata, collect_all"
        in spec_source
    ), (
        "Expected `from PyInstaller.utils.hooks import collect_all, "
        "copy_metadata` (or symmetric ordering) — the existing collect_all "
        "import line should be extended, not duplicated on a separate line."
    )


def test_spec_includes_copy_metadata_for_musicstreamer(spec_source: str) -> None:
    """Phase 65 D-08 / VER-02-H: spec calls copy_metadata("musicstreamer")
    so dist-info ships in the bundle. Accept either single- or double-quoted
    argument; the project does not enforce a quote style here."""
    has_call = (
        'copy_metadata("musicstreamer")' in spec_source
        or "copy_metadata('musicstreamer')" in spec_source
    )
    assert has_call, (
        "MusicStreamer.spec must call copy_metadata('musicstreamer') so the "
        "bundle ships musicstreamer.dist-info. Without this, "
        "importlib.metadata.version('musicstreamer') raises "
        "PackageNotFoundError inside the bundled exe at MainWindow "
        "construction time."
    )


def test_spec_concatenates_ms_datas_into_datas_list(spec_source: str) -> None:
    """Phase 65 D-08: the result of copy_metadata is appended to the datas
    list — proves the import isn't dead code and that dist-info actually
    ships. The variable name follows the existing _cn_datas / _sl_datas /
    _yt_datas convention."""
    assert "_ms_datas = copy_metadata" in spec_source, (
        "Expected `_ms_datas = copy_metadata(...)` assignment alongside "
        "the existing _cn_datas / _sl_datas / _yt_datas collect_all peers."
    )
    assert "+ _ms_datas" in spec_source, (
        "Expected `+ _ms_datas` in the datas concatenation at the "
        "Analysis(...) block — proves the dist-info actually ships in "
        "the bundle (not just imported and forgotten)."
    )


def test_spec_has_no_try_except_around_copy_metadata(spec_source: str) -> None:
    """Phase 65 D-08 (negative): CONTEXT explicitly prohibits a try/except
    fallback to a placeholder version. The bundle must fail loudly with
    PackageNotFoundError if metadata is missing, not ship a silent
    placeholder string. This regression-lock catches a future "well-meaning"
    defensive edit that would mask a broken install.

    Heuristic: scan the 200 bytes BEFORE the copy_metadata call site for
    `try:` / `PackageNotFoundError` tokens. This is intentionally a coarse
    proximity check — it catches the realistic regression shape (defensive
    wrap directly around the call) without requiring a full Python AST
    parse of the spec. If a future spec edit legitimately needs an
    unrelated try block within 200 bytes of the copy_metadata call, this
    test should be updated to anchor more precisely on the copy_metadata
    call's enclosing block (e.g. via ast.parse + walking the tree)."""
    # Find the copy_metadata call site and check the surrounding 200 chars.
    idx = spec_source.find('copy_metadata("musicstreamer")')
    if idx == -1:
        idx = spec_source.find("copy_metadata('musicstreamer')")
    assert idx != -1, "copy_metadata('musicstreamer') call not found"
    # Look at the 200 bytes BEFORE the call (and 100 bytes after) for
    # `try:` or `PackageNotFoundError` tokens — see docstring for the
    # heuristic limitation.
    nearby = spec_source[max(0, idx - 200) : idx + 100]
    assert "try:" not in nearby, (
        "Phase 65 D-08 explicit prohibition: NO try/except wrapping "
        "copy_metadata. Bundle must fail loudly if metadata is missing."
    )
    assert "PackageNotFoundError" not in nearby, (
        "Phase 65 D-08 explicit prohibition: NO PackageNotFoundError catch "
        "around copy_metadata. Hard fail at build time is the contract."
    )
