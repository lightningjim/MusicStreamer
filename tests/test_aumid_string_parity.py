"""Phase 56 / D-09 #3: AUMID literal parity between __main__.py and MusicStreamer.iss.

A typo in either file silently breaks the SMTC overlay binding without any
runtime error or Linux-CI test failure. This guard catches drift at unit-test
time (Linux-CI safe -- no Windows dependency).

Mitigates T-56-02 (Tampering: silent AUMID drift causes packaging regression).
"""
import re
from pathlib import Path


def test_aumid_string_parity():
    """D-09 #3: __main__.py and MusicStreamer.iss must declare the same AUMID literal."""
    repo_root = Path(__file__).parent.parent
    main_py = (repo_root / "musicstreamer" / "__main__.py").read_text()
    iss = (repo_root / "packaging" / "windows" / "MusicStreamer.iss").read_text()
    main_match = re.search(r'app_id:\s*str\s*=\s*"([^"]+)"', main_py)
    iss_match = re.search(r'AppUserModelID:\s*"([^"]+)"', iss)
    assert main_match is not None, (
        "AUMID default arg not found in musicstreamer/__main__.py "
        "(expected pattern: app_id: str = \"...\")"
    )
    assert iss_match is not None, (
        "AppUserModelID directive not found in packaging/windows/MusicStreamer.iss "
        "(expected pattern: AppUserModelID: \"...\")"
    )
    assert main_match.group(1) == iss_match.group(1), (
        f"AUMID drift: __main__.py='{main_match.group(1)}' "
        f"iss='{iss_match.group(1)}'"
    )
