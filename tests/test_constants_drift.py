"""Phase 61 D-02 drift guard: constants.APP_ID is the single source of truth.

These tests fail loud if the .desktop file basename or icon basename ever
drifts away from constants.APP_ID, or if the org.example.MusicStreamer
placeholder leaks back into musicstreamer/ Python sources. Runs in <100ms;
addresses the silent-failure mode flagged by RESEARCH.md §Pitfall 6.

Phase 71 / T-40-04 invariant (appended): the literal grep count of
`setTextFormat(Qt.RichText)` across `musicstreamer/` MUST NOT increase. The
baseline today is 4 (3 in now_playing_panel.py at lines 355, 617, 633;
1 in edit_station_dialog.py at line 487). Plan 71-03 removes the
EditStationDialog occurrence → EXPECTED_RICHTEXT_COUNT = 3. This test is
RED today (count=4) and turns GREEN after Plan 71-03 lands.
"""
from pathlib import Path

from musicstreamer import constants


# Phase 71 / T-40-04 baseline: post-Plan-71-03 expected literal count.
EXPECTED_RICHTEXT_COUNT = 3


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


def test_richtext_baseline_unchanged_by_phase_71():
    """T-40-04 / Phase 71 invariant: count of setTextFormat(Qt.RichText)
    across musicstreamer/ must match EXPECTED_RICHTEXT_COUNT (3).

    Today's grep count is 4 (this test is RED). Plan 71-03 removes the
    EditStationDialog _sibling_label QLabel → count drops to 3. Plan 71
    must NOT add any new setTextFormat(Qt.RichText) call.

    The strict literal pattern `setTextFormat(Qt.RichText)` ensures comments
    mentioning "RichText" do not accidentally match — only the actual API
    call counts.
    """
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "setTextFormat(Qt.RichText)"
    count = 0
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count += text.count(needle)
    assert count == EXPECTED_RICHTEXT_COUNT, (
        f"T-40-04 / Phase 71: expected {EXPECTED_RICHTEXT_COUNT} "
        f"setTextFormat(Qt.RichText) calls in musicstreamer/, found {count}. "
        "Phase 71 must not add new RichText labels; Plan 71-03 removes "
        "the EditStationDialog._sibling_label QLabel (baseline 4 → 3)."
    )


# ---------------------------------------------------------------------------
# Phase 74 / SOMA-NN drift guards (appended — do NOT modify existing tests above)
# ---------------------------------------------------------------------------


def test_soma_import_logger_registered():
    """D-16 / SOMA-16: __main__.py must wire musicstreamer.soma_import at logging.INFO.

    RED until Plan 03 modifies musicstreamer/__main__.py to add:
        logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)

    Per CONTEXT D-16: same INFO-level treatment as musicstreamer.player
    (which is the only current per-logger registration in __main__.py).
    Maps to RESEARCH test #17.
    """
    main_path = Path(__file__).parent.parent / "musicstreamer" / "__main__.py"
    text = main_path.read_text(encoding="utf-8")
    needle = 'logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)'
    assert needle in text, (
        "D-16 / SOMA-16: __main__.py must register musicstreamer.soma_import logger at INFO. "
        f"Looked for literal: {needle!r}. "
        "This test goes GREEN when Plan 03 appends the setLevel line to main()."
    )


def test_soma_nn_requirements_registered():
    """SOMA-01..SOMA-17: all 17 requirement IDs must appear in REQUIREMENTS.md.

    GREEN immediately after Plan 01 Task 1 lands (this plan). Acts as a
    self-verification that the SOMA-NN block was added correctly.
    Maps to RESEARCH test #13.
    """
    req_path = Path(__file__).parent.parent / ".planning" / "REQUIREMENTS.md"
    text = req_path.read_text(encoding="utf-8")
    soma_ids = [
        "SOMA-01", "SOMA-02", "SOMA-03", "SOMA-04", "SOMA-05",
        "SOMA-06", "SOMA-07", "SOMA-08", "SOMA-09", "SOMA-10",
        "SOMA-11", "SOMA-12", "SOMA-13", "SOMA-14", "SOMA-15",
        "SOMA-16", "SOMA-17",
    ]
    for req_id in soma_ids:
        assert req_id in text, (
            f"REQUIREMENTS.md missing {req_id} after Phase 74. "
            "Plan 01 Task 1 must register all SOMA-01..SOMA-17 rows."
        )
