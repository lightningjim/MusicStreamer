"""Update yt-dlp across every place this project pins it, in one shot.

yt-dlp ships a new release roughly monthly. Updating it correctly means
touching THREE things in lockstep — miss one and you ship a stale or
hash-mismatched bundle:

  1. uv.lock          — the dev/runtime pin (`uv lock --upgrade-package yt-dlp`)
  2. the venv         — reconciled WITH the `test` extra (`uv sync --extra test`);
                        a bare `uv sync` prunes pytest/pytest-qt (PEP 621 extra).
  3. python3-modules.yaml — the Flatpak module hardcodes the wheel URL + sha256;
                        it does NOT track uv.lock and must be rewritten from it.

Windows (`packaging/windows/MusicStreamer.spec`, `collect_all("yt_dlp")`) and
`tools/linux-flatpak/flatpak-requirements.txt` (unpinned) pick up the installed
version automatically — they need no edit, only a rebuild.

This script runs steps 1-3, then the yt-dlp-touching test suites (drift guards +
packaging-manifest parse), and prints what still needs a human (commit, rebuild).
It is idempotent: re-running when already current is a no-op that still verifies.

Usage (from repo root):
    python tools/update_yt_dlp.py            # upgrade, sync, patch manifest, test
    python tools/update_yt_dlp.py --check    # report current vs locked; change nothing
    python tools/update_yt_dlp.py --no-test  # skip the test run (faster; not advised)

Exit codes:
    0 — success (update landed and tests passed) OR --check found nothing stale
    1 — a step failed (uv error, manifest pattern not found, or tests failed)
    2 — --check found the Flatpak manifest out of sync with uv.lock
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# The Flatpak manifest pins exactly one yt_dlp wheel: a `url:` line pointing at
# a *-py3-none-any.whl on files.pythonhosted.org, followed by its `sha256:` line.
# Capture group 1 = the indentation before sha256 so we preserve YAML structure
# (anchors/aliases elsewhere in the file are never touched). VERIFIED against the
# live python3-modules.yaml: exactly one match.
_MANIFEST_WHEEL_RE = re.compile(
    r"url: https://files\.pythonhosted\.org/\S*?yt_dlp-\S+?-py3-none-any\.whl\n"
    r"(\s+)sha256: [0-9a-f]{64}"
)


def _repo_root() -> Path:
    # tools/update_yt_dlp.py -> repo root is parent.parent.
    return Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command, streaming output, returning the completed process."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, text=True)


def locked_wheel(lock_text: str) -> tuple[str, str, str]:
    """Return (version, wheel_url, sha256) for yt-dlp from uv.lock text.

    Raises SystemExit(1) if yt-dlp or its py3-none-any wheel is absent.
    """
    data = tomllib.loads(lock_text)
    for pkg in data.get("package", []):
        if pkg.get("name") != "yt-dlp":
            continue
        version = pkg.get("version", "?")
        for wheel in pkg.get("wheels", []):
            url = wheel.get("url", "")
            if url.endswith("-py3-none-any.whl"):
                sha = wheel.get("hash", "")
                if sha.startswith("sha256:"):
                    sha = sha[len("sha256:"):]
                return version, url, sha
        sys.exit("ERROR: yt-dlp in uv.lock has no py3-none-any wheel")
    sys.exit("ERROR: yt-dlp not found in uv.lock")


def patch_manifest(manifest_path: Path, url: str, sha256: str) -> bool:
    """Rewrite the yt-dlp wheel url+sha256 in the Flatpak manifest.

    Returns True if the file changed, False if it was already current.
    Raises SystemExit(1) if the expected wheel block is not found exactly once.
    """
    text = manifest_path.read_text()
    matches = _MANIFEST_WHEEL_RE.findall(text)
    if len(matches) != 1:
        sys.exit(
            f"ERROR: expected exactly 1 yt_dlp wheel block in "
            f"{manifest_path.name}, found {len(matches)}"
        )
    new_text = _MANIFEST_WHEEL_RE.sub(
        f"url: {url}\n\\g<1>sha256: {sha256}", text
    )
    if new_text == text:
        return False
    manifest_path.write_text(new_text)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update yt-dlp everywhere it is pinned.")
    parser.add_argument(
        "--check", action="store_true",
        help="report current vs locked and whether the manifest is in sync; change nothing",
    )
    parser.add_argument(
        "--no-test", action="store_true",
        help="skip the yt-dlp test suite after updating (faster; not advised)",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    lock_path = root / "uv.lock"
    manifest_path = root / "python3-modules.yaml"

    # --check: compare the manifest's pinned wheel against uv.lock; no mutation.
    if args.check:
        version, url, sha = locked_wheel(lock_path.read_text())
        print(f"uv.lock pins yt-dlp {version}")
        manifest_text = manifest_path.read_text()
        if f"sha256: {sha}" in manifest_text and url in manifest_text:
            print(f"Flatpak manifest is in sync ({manifest_path.name}).")
            return 0
        print(f"Flatpak manifest is OUT OF SYNC — run without --check to fix.")
        return 2

    # 1 + 2: bump the lock and reconcile the venv WITH the test extra.
    print("[1/4] Upgrading yt-dlp in uv.lock ...")
    if _run(["uv", "lock", "--upgrade-package", "yt-dlp"], root).returncode != 0:
        return 1
    print("[2/4] Syncing venv (with test extra) ...")
    if _run(["uv", "sync", "--extra", "test"], root).returncode != 0:
        return 1

    # 3: rewrite the Flatpak wheel from whatever uv.lock now resolves to.
    version, url, sha = locked_wheel(lock_path.read_text())
    print(f"[3/4] Patching Flatpak manifest -> yt-dlp {version} ...")
    changed = patch_manifest(manifest_path, url, sha)
    print(f"  {manifest_path.name}: {'updated' if changed else 'already current'}")

    # 4: prove the upgrade is safe — drift guards + manifest-parse packaging tests.
    if not args.no_test:
        print("[4/4] Running yt-dlp + packaging tests ...")
        tests = [
            "tests/test_yt_dlp_opts.py",
            "tests/test_yt_dlp_opts_drift.py",
            "tests/test_player_node_runtime.py",
            "tests/test_yt_import_library.py",
            "tests/test_cookies.py",
            "tests/test_packaging_linux_spec.py",
            "tests/test_packaging_spec.py",
        ]
        if _run([sys.executable, "-m", "pytest", *tests, "-q"], root).returncode != 0:
            print("\nTests FAILED — yt-dlp internals may have shifted. Review before committing.")
            return 1
    else:
        print("[4/4] Skipped tests (--no-test).")

    print(
        f"\nyt-dlp updated to {version}. Still TODO (human):\n"
        f"  - git add uv.lock python3-modules.yaml && commit\n"
        f"  - rebuild Windows + Flatpak bundles to ship the new version\n"
        f"    (their pins auto-track; they just need a fresh build)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
