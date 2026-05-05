"""Phase 61 D-02 drift guard: constants.APP_ID is the single source of truth.

These tests fail loud if the .desktop file basename or icon basename ever
drifts away from constants.APP_ID, or if the org.example.MusicStreamer
placeholder leaks back into musicstreamer/ Python sources. Runs in <100ms;
addresses the silent-failure mode flagged by RESEARCH.md §Pitfall 6.
"""
from pathlib import Path

from musicstreamer import constants


def test_app_id_is_lightningjim_and_matches_phase_56_aumid():
    """The Linux app id and the Windows AUMID must match (Phase 61 D-01)."""
    assert constants.APP_ID == "org.lightningjim.MusicStreamer"


def test_bundled_desktop_basename_matches_app_id():
    """packaging/linux/<APP_ID>.desktop must exist."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.desktop"
    assert expected.exists(), (
        f"Bundled .desktop name must match constants.APP_ID. "
        f"Looked for: {expected}. "
        f"Found .desktop files in {pkg_dir}: "
        f"{sorted(p.name for p in pkg_dir.glob('*.desktop'))}"
    )


def test_bundled_icon_basename_matches_app_id():
    """packaging/linux/<APP_ID>.png must exist."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.png"
    assert expected.exists()


def test_no_org_example_literal_remains_in_python_sources():
    """No code under musicstreamer/ should reference the old placeholder."""
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "org.example.MusicStreamer"
    hits = []
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in text:
            hits.append(str(py.relative_to(pkg_root.parent)))
    assert not hits, f"Phase 61 left placeholder behind in: {hits}"


def test_dev_launch_script_app_id_matches_constants():
    """scripts/dev-launch.sh hardcodes APP_ID for the systemd scope name; keep it in sync.

    The shell script can't import musicstreamer.constants, so the value is
    duplicated. This test fails loud if anyone bumps constants.APP_ID without
    also updating the script — preventing the systemd scope unit from
    resolving to a stale app id (which would re-trigger the BUG-08 dock/icon
    symptom under the dev-launch path).
    """
    script = Path(__file__).parent.parent / "scripts" / "dev-launch.sh"
    text = script.read_text(encoding="utf-8")
    expected = f'APP_ID="{constants.APP_ID}"'
    assert expected in text, (
        f"scripts/dev-launch.sh must declare {expected!r} verbatim "
        f"(found APP_ID lines: "
        f"{[ln for ln in text.splitlines() if 'APP_ID=' in ln]})"
    )
