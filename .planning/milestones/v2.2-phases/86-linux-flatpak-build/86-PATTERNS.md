# Phase 86: Linux Flatpak Build - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 9 new/modified files
**Analogs found:** 8 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `io.github.kcreasey.MusicStreamer.yaml` | config (manifest) | transform | `tools/linux-build/environment.yml` (dep-list) | partial-match (YAML build artifact; no Flatpak analog exists yet) |
| `python3-modules.yaml` | config (generated) | transform | `tools/linux-build/environment.yml` | partial-match (generated dep list) |
| `tools/linux-flatpak/build.sh` | utility (build driver) | batch | `tools/linux-build/build.sh` | exact |
| `tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop` | config | — | `tools/linux-build/desktop/org.lightningjim.MusicStreamer.desktop` | exact |
| `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` | config | — | no existing analog | none |
| `.github/workflows/linux-flatpak.yml` | config (CI) | request-response | `.github/workflows/linux-appimage.yml` | exact |
| `tests/test_packaging_spec.py` (extended) | test | CRUD | `tests/test_packaging_linux_spec.py` (AppImage guards) | exact |
| `musicstreamer/flatpak_first_launch.py` | utility | file-I/O | `musicstreamer/paths.py` + `musicstreamer/settings_export.py` | role-match |
| `musicstreamer/ui_qt/flatpak_import_wizard.py` | component | request-response | `musicstreamer/ui_qt/settings_import_dialog.py` | exact |

---

## Pattern Assignments

### `tools/linux-flatpak/build.sh` (utility, batch)

**Analog:** `tools/linux-build/build.sh`

**GPG fail-fast pattern** (lines 82–85):
```bash
if [[ -z "${GPG_KEY_ID:-}" && "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_FAIL reason=gpg_key_unset (set GPG_KEY_ID=<keyid> or SKIP_SIGN=1 for local iteration; CI must set the key) (D-09)" >&2
  exit 5
fi
```

**Repo root / artifacts layout pattern** (lines 87–93):
```bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${HERE}/artifacts"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
mkdir -p "${ARTIFACTS}"
```

**GPG signing pattern** (lines 390–398):
```bash
if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  GPG_BIN="$(command -v gpg2 || command -v gpg || true)"
  [[ -n "$GPG_BIN" ]] || { echo "BUILD_FAIL reason=no_gpg (install gnupg / gnupg2)" >&2; exit 6; }
  "$GPG_BIN" --detach-sign --armor --local-user "$GPG_KEY_ID" --output "${APPIMG}.sig" "$APPIMG" \
    || { echo "BUILD_FAIL reason=signing_failed ($GPG_BIN --detach-sign exited non-zero for key=$GPG_KEY_ID)" >&2; exit 6; }
  echo "SIGN_OK signature=${APPIMG}.sig key=$GPG_KEY_ID gpg=$GPG_BIN"
else
  echo "SIGN_SKIPPED SKIP_SIGN=1 (local-iteration mode; no .sig sidecar produced)"
fi
```

**Exit code convention** (lines 1–11, comment header):
```
# Exit codes:
#   0 = artifact produced
#   1 = env missing
#   2 = build failed
#   5 = GPG_KEY_ID unset and SKIP_SIGN != 1
#   6 = gpg signing failed
```

**Key differences for Flatpak build.sh:**
- Replace docker + linuxdeploy invocation with `flatpak-builder --user --repo=flatpak-repo --force-clean build-dir io.github.kcreasey.MusicStreamer.yaml`
- Replace GLIBC scan step with `appstreamcli validate` + `desktop-file-validate` pre-flight gate
- Replace `gpg --detach-sign` sidecar with `flatpak build-bundle --gpg-sign="$GPG_KEY_ID"` (signing is inline in the bundle, not a sidecar; see RESEARCH.md Pattern 6)
- `SKIP_SIGN`, `GPG_KEY_ID`, exit-code structure, `BUILD_FAIL reason=` prefix — copy verbatim

---

### `.github/workflows/linux-flatpak.yml` (CI config, request-response)

**Analog:** `.github/workflows/linux-appimage.yml`

**Trigger + permissions pattern** (lines 14–22):
```yaml
name: Linux AppImage Build

on:
  workflow_dispatch:

permissions:
  contents: read
```

**Secrets validation pattern** (lines 42–52):
```yaml
- name: Validate signing secrets (D-16 fail-fast)
  env:
    LINUX_SIGNING_KEY: ${{ secrets.LINUX_SIGNING_KEY }}
    LINUX_SIGNING_KEY_ID: ${{ secrets.LINUX_SIGNING_KEY_ID }}
  run: |
    set -euo pipefail
    if [[ -z "${LINUX_SIGNING_KEY:-}" || -z "${LINUX_SIGNING_KEY_ID:-}" ]]; then
      echo "WORKFLOW_FAIL: signing secrets missing (set LINUX_SIGNING_KEY and LINUX_SIGNING_KEY_ID in repo secrets)" >&2
      exit 1
    fi
    echo "SECRETS_OK key_id_present=true key_block_length=${#LINUX_SIGNING_KEY}"
```

**GPG import pattern** (lines 54–73):
```yaml
- name: Import signing key into ephemeral GNUPGHOME (D-16)
  env:
    LINUX_SIGNING_KEY: ${{ secrets.LINUX_SIGNING_KEY }}
    LINUX_SIGNING_KEY_ID: ${{ secrets.LINUX_SIGNING_KEY_ID }}
  run: |
    set -euo pipefail
    GNUPGHOME="$(mktemp -d)"
    echo "GNUPGHOME=${GNUPGHOME}" >> "$GITHUB_ENV"
    chmod 700 "${GNUPGHOME}"
    echo "allow-loopback-pinentry" >> "${GNUPGHOME}/gpg-agent.conf"
    echo "pinentry-mode loopback" >> "${GNUPGHOME}/gpg.conf"
    printf '%s' "${LINUX_SIGNING_KEY}" | gpg --batch --import
    echo "GPG_KEY_ID=${LINUX_SIGNING_KEY_ID}" >> "$GITHUB_ENV"
```

**Artifact upload pattern** (lines 121–130):
```yaml
- name: Upload AppImage + signature as workflow artifacts
  uses: actions/upload-artifact@v4
  with:
    name: MusicStreamer-AppImage
    path: |
      tools/linux-build/artifacts/MusicStreamer-*.AppImage
      tools/linux-build/artifacts/MusicStreamer-*.AppImage.sig
    if-no-files-found: error
    retention-days: 30
```

**GNUPGHOME scrub pattern** (lines 131–137):
```yaml
- name: Scrub ephemeral GNUPGHOME (defense-in-depth)
  if: always()
  run: |
    if [[ -n "${GNUPGHOME:-}" && -d "${GNUPGHOME}" ]]; then
      rm -rf "${GNUPGHOME}"
      echo "SCRUBBED ${GNUPGHOME}"
    fi
```

**Key differences for linux-flatpak.yml:**
- Job name: `Build signed Flatpak (org.kde.Platform//6.8)`
- No `ubuntu-22.04` runner requirement (Flatpak bundles its own runtime; GLIBC baseline concern is moot). Use `ubuntu-latest` or the official `flatpak/flatpak-github-actions` container.
- Replace Docker prerequisite install with `flatpak-builder` prerequisite: `sudo apt-get install -y flatpak-builder` + `flatpak install --user flathub org.kde.Platform//6.8 org.kde.Sdk//6.8 io.qt.PySide.BaseApp//6.8`
- No GLIBC scan step; replace with `appstreamcli validate` + `desktop-file-validate` (already in build.sh)
- No AppImage smoke step (no desktop session; CI success = bundle builds + validators pass per D-07)
- Artifact path: `tools/linux-flatpak/artifacts/MusicStreamer-*.flatpak` (no `.sig` sidecar — GPG signing is inline in `flatpak build-bundle`)
- Add `container: options: --privileged` to job config (FUSE/OSTree requirement — RESEARCH.md Pitfall 9)
- `GNUPGHOME` scrub and secrets validation steps: copy verbatim

---

### `tests/test_packaging_spec.py` (test, CRUD) — extended with Flatpak guards

**Analog:** `tests/test_packaging_linux_spec.py`

**Path constant pattern** (lines 25–40):
```python
_BUILD_SH = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "build.sh"
)
_APPRUN = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "AppRun"
)
_ENVYML = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "environment.yml"
)
_DESKTOP = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-build" / "desktop" / "org.lightningjim.MusicStreamer.desktop"
)
```

**Module-scope fixture pattern** (lines 43–46):
```python
@pytest.fixture(scope="module")
def build_sh_source() -> str:
    assert _BUILD_SH.is_file(), f"expected build.sh at {_BUILD_SH}"
    return _BUILD_SH.read_text(encoding="utf-8")
```

**Comment-strip helper pattern** (lines 73–79):
```python
def _strip_comments_sh(source: str) -> str:
    """Strip shell-comment lines for negative-assertion gates."""
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
```

**GPG guard pattern** (lines 187–197):
```python
def test_build_sh_fail_fast_when_gpg_key_unset(build_sh_source: str) -> None:
    assert "BUILD_FAIL reason=gpg_key_unset" in build_sh_source
    assert "exit 5" in build_sh_source
    executable = _strip_comments_sh(build_sh_source)
    assert "SKIP_SIGN" in executable, (
        "build.sh must reference SKIP_SIGN in an executable (non-comment) "
        "line so the local-iteration escape hatch works (D-09)."
    )
```

**New Flatpak guards to add — follow the same fixture + assertion shape:**

```python
# --- New path constants for Flatpak section ---
_FLATPAK_MANIFEST = (
    Path(__file__).resolve().parent.parent / "io.github.kcreasey.MusicStreamer.yaml"
)
_PYTHON3_MODULES = (
    Path(__file__).resolve().parent.parent / "python3-modules.yaml"
)
_FLATPAK_DESKTOP = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-flatpak" / "desktop"
    / "io.github.kcreasey.MusicStreamer.desktop"
)
_FLATPAK_METAINFO = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-flatpak" / "metainfo"
    / "io.github.kcreasey.MusicStreamer.metainfo.xml"
)
_FLATPAK_BUILD_SH = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-flatpak" / "build.sh"
)

# --- Module-scope YAML fixture ---
@pytest.fixture(scope="module")
def manifest_data():
    import yaml
    assert _FLATPAK_MANIFEST.is_file(), f"expected manifest at {_FLATPAK_MANIFEST}"
    return yaml.safe_load(_FLATPAK_MANIFEST.read_text())

# --- Allow-list guard (D-13) ---
def test_flatpak_finish_args_allow_list(manifest_data):
    args = manifest_data["finish-args"]
    assert "--share=network" in args
    assert "--socket=pulseaudio" in args
    assert "--socket=wayland" in args
    assert "--socket=fallback-x11" in args
    assert "--own-name=org.mpris.MediaPlayer2.MusicStreamer" in args
    assert "--filesystem=~/.local/share/musicstreamer:ro" in args
    assert "--env=QTWEBENGINE_DISABLE_SANDBOX=1" in args

# --- Deny-list guard (D-13, security-critical) ---
def test_flatpak_finish_args_deny_list(manifest_data):
    """Security-critical: absence of forbidden permissions."""
    args = manifest_data["finish-args"]
    assert "--filesystem=home" not in args, "broad home filesystem NOT permitted"
    assert "--filesystem=home:rw" not in args
    assert "--socket=session-bus" not in args, "broad session-bus NOT permitted"

# --- Runtime pin guard (D-13) ---
def test_flatpak_runtime_version_pins(manifest_data):
    assert manifest_data["runtime-version"] == "6.8"
    assert manifest_data["base-version"] == "6.8"
    extensions = manifest_data.get("add-extensions", {})
    ffmpeg = extensions.get("org.freedesktop.Platform.ffmpeg-full", {})
    assert ffmpeg.get("version") == "24.08"
```

**subprocess validator pattern — copy from RESEARCH.md §Code Examples (lines 558–583), following the `skipif+subprocess.run` idiom already in test_packaging_spec.py for desktop-file guards.**

---

### `io.github.kcreasey.MusicStreamer.yaml` (config/manifest, transform)

**No direct codebase analog** — Flatpak YAML manifests are a new artifact type for this project.

**Closest structural analog:** `tools/linux-build/environment.yml` — similarly a YAML build-input file that declares the dep graph consumed by the build driver. The pattern is: declare deps at the top level, keep it as the single source of truth, parse it in tests.

**Concrete template** from RESEARCH.md Pattern 1 (lines 248–297) — use verbatim as the authoring starting point. Key decisions already locked:
- `base: io.qt.PySide.BaseApp` / `base-version: '6.8'`
- Do NOT set `BASEAPP_REMOVE_WEBENGINE=1` (GBS.FM login requires QtWebEngineWidgets — RESEARCH.md Pitfall 1)
- `cleanup-commands` must include `mkdir -p ${FLATPAK_DEST}/lib/ffmpeg` (RESEARCH.md Pitfall 2)
- node20 copy step: `install -D /usr/lib/sdk/node20/bin/node /app/bin/node` (RESEARCH.md Pattern 2)
- finish-args verbatim from RESEARCH.md §Code Examples (lines 484–496)

---

### `python3-modules.yaml` (config/generated, transform)

**No codebase analog** — generated output from `flatpak-pip-generator`.

**Analog for how it is declared and committed:** `tools/linux-build/environment.yml` — that file is also committed to the repo as the single source of truth for a dep list and parsed in tests.

**Generation command** (RESEARCH.md lines 138–152):
```bash
flatpak-pip-generator \
  --runtime='org.kde.Sdk//6.8' \
  --yaml \
  --output python3-modules \
  yt-dlp streamlink platformdirs chardet mutagen pillow requests
```

**Critical exclusion:** Do NOT include `PySide6` — it conflicts with BaseApp (RESEARCH.md Pitfall 5). Use a curated `flatpak-requirements.txt` rather than pyproject.toml directly.

**Drift-guard test** (RESEARCH.md Validation §PKG-LIN-FP-09):
```python
def test_python3_modules_yaml_exists(tmp_path):
    import yaml
    assert _PYTHON3_MODULES.is_file(), f"python3-modules.yaml not found at {_PYTHON3_MODULES}"
    data = yaml.safe_load(_PYTHON3_MODULES.read_text())
    assert data is not None, "python3-modules.yaml must be valid YAML"
```

---

### `tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop` (config)

**Analog:** `tools/linux-build/desktop/org.lightningjim.MusicStreamer.desktop` (lines 1–14)

**Full source to copy and adapt:**
```ini
[Desktop Entry]
Type=Application
Name=MusicStreamer
GenericName=Internet Radio
# PKG-LIN-APP-09: playlist MIME types (.pls, .m3u) are intentionally absent
# (curated-library identity; playlist files are import inputs, not file-open targets).
Exec=musicstreamer %U
Icon=org.lightningjim.MusicStreamer
Categories=AudioVideo;Audio;Music;Player;
Comment=Internet radio stream player
Keywords=radio;stream;music;internet;
MimeType=audio/mpeg;audio/aac;audio/x-aac;audio/mp4;audio/ogg;audio/flac;audio/wav;audio/webm;
StartupNotify=true
StartupWMClass=MusicStreamer
```

**Changes for Flatpak version:**
- `Icon=io.github.kcreasey.MusicStreamer` (match the new app ID, not the old `org.lightningjim.*`)
- `Exec=musicstreamer %U` stays identical (the `command:` in the manifest sets the binary name)
- Preserve the PKG-LIN-APP-09 comment and absence of `audio/x-mpegurl` / `audio/x-scpls`
- The existing `test_desktop_file_has_no_playlist_mime_entries` in `test_packaging_linux_spec.py` is the drift-guard model

---

### `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` (config)

**No codebase analog** — first AppStream metainfo file in the project.

**Structural reference** from RESEARCH.md §Appstream + Desktop File (and RESEARCH.md Code Examples lines 558–575). Minimum required fields per `appstreamcli validate`:
- `<id>io.github.kcreasey.MusicStreamer</id>`
- `<name>MusicStreamer</name>`
- `<summary>...</summary>`
- `<description>...</description>`
- `<url type="homepage">...</url>`
- `<releases>` with at least one `<release version="..." date="..."/>`
- `<content_rating type="oars-1.1">` block
- At least one `<screenshot>` (RESEARCH.md Open Question 6)

The `appstreamcli validate` pytest guard (skip-if-not-installed pattern) is the correctness gate — see `test_packaging_spec.py` additions above.

---

### `musicstreamer/flatpak_first_launch.py` (utility, file-I/O)

**Analog:** `musicstreamer/paths.py` (same module role: pure path/detection logic, no Qt dependency)

**Pure-module import pattern** from `paths.py` (lines 1–32):
```python
"""Single source of truth for MusicStreamer data paths."""
from __future__ import annotations

import os
import platformdirs

_root_override: str | None = None

def _root() -> str:
    if _root_override is not None:
        return _root_override
    return platformdirs.user_data_dir("musicstreamer")
```

**Key insight from paths.py lines 28–31:** Inside the Flatpak sandbox, `platformdirs.user_data_dir("musicstreamer")` resolves to `~/.var/app/io.github.kcreasey.MusicStreamer/data/musicstreamer` because Flatpak overrides `XDG_DATA_HOME`. The host unsandboxed path `~/.local/share/musicstreamer` is a LITERAL constant, not routed through `paths.data_dir()` (RESEARCH.md Pitfall 7).

**Detection pattern** (from RESEARCH.md §Code Examples lines 539–556 — mirrors the `paths.py` pure-function style):
```python
from __future__ import annotations

import os

# Literal host path accessible via the narrow :ro finish-arg mount (D-01).
# Must NOT use paths.data_dir() — inside the sandbox that returns the
# sandbox-remapped path, not the host path (RESEARCH.md Pitfall 7).
_HOST_DATA_DIR = os.path.expanduser("~/.local/share/musicstreamer")
_HOST_DB = os.path.join(_HOST_DATA_DIR, "musicstreamer.sqlite3")

def has_unsandboxed_data() -> bool:
    """True if old unsandboxed data exists at the narrow :ro mount."""
    return os.path.isfile(_HOST_DB)

def import_offered_flag_path() -> str:
    """Flag file in sandbox data dir — presence means wizard was already offered."""
    from musicstreamer import paths
    return os.path.join(paths.data_dir(), ".flatpak-import-offered")

def should_offer_import_wizard() -> bool:
    return has_unsandboxed_data() and not os.path.isfile(import_offered_flag_path())
```

**Second analog:** `musicstreamer/settings_export.py` (lines 73–100) for the `_validate_zip_members` security guard that is called again at import (RESEARCH.md Security §V5). The import path reuses `settings_export.preview_import` + `settings_export.commit_import` verbatim (D-04) — no new import logic is invented here.

---

### `musicstreamer/ui_qt/flatpak_import_wizard.py` (component, request-response)

**Analog:** `musicstreamer/ui_qt/settings_import_dialog.py`

**Imports pattern** (lines 1–43):
```python
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    ...
)

from musicstreamer.settings_export import ImportPreview, commit_import
from musicstreamer.repo import Repo, db_connect
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR
```

**Background-worker threading pattern** (lines 50–74):
```python
class _ImportCommitWorker(QThread):
    commit_done = Signal()
    commit_error = Signal(str)

    def __init__(self, preview: ImportPreview, mode: str, parent=None):
        super().__init__(parent)
        self._preview = preview
        self._mode = mode

    def run(self) -> None:
        try:
            repo = Repo(db_connect())
            commit_import(self._preview, repo, self._mode)
            self.commit_done.emit()
        except Exception as exc:
            self.commit_error.emit(str(exc))
```

**Signal connection pattern** (lines 223–230):
```python
self._commit_worker = _ImportCommitWorker(self._preview, mode, parent=self)
self._commit_worker.commit_done.connect(
    self._on_commit_done, Qt.QueuedConnection
)
self._commit_worker.commit_error.connect(
    self._on_commit_error, Qt.QueuedConnection
)
self._commit_worker.start()
```

**Key additions for flatpak_import_wizard.py vs SettingsImportDialog:**
- Constructor takes no `preview` argument at init time — wizard builds it on the fly by opening the source Repo against the `:ro` host path and calling `settings_export.build_zip` + `settings_export.preview_import` internally
- Add "offer-once" flag write on dismiss: `open(import_offered_flag_path(), "w").close()`
- The rest of the dialog layout (mode radio, summary label, detail tree, button box) is copy from `SettingsImportDialog` lines 82–197

---

## Shared Patterns

### GPG Signing Discipline
**Source:** `tools/linux-build/build.sh` lines 82–85 (fail-fast), lines 390–398 (sign step)
**Apply to:** `tools/linux-flatpak/build.sh`

Reuse verbatim: `SKIP_SIGN`, `GPG_KEY_ID`, `command -v gpg2 || command -v gpg`, `BUILD_FAIL reason=gpg_key_unset` (exit 5), `BUILD_FAIL reason=signing_failed` (exit 6). The only difference is the signing command: `flatpak build-bundle --gpg-sign="$GPG_KEY_ID"` instead of `gpg --detach-sign --armor`.

### CI Secrets + Ephemeral GNUPGHOME
**Source:** `.github/workflows/linux-appimage.yml` lines 42–73
**Apply to:** `.github/workflows/linux-flatpak.yml`

Copy the secrets validation step, `mktemp -d` GNUPGHOME, `allow-loopback-pinentry` + `pinentry-mode loopback` config, `gpg --batch --import`, and the `if: always()` scrub step verbatim.

### BUILD_FAIL / BUILD_OK Diagnostic Prefix
**Source:** `tools/linux-build/build.sh` — `BUILD_FAIL reason=...`, `BUILD_OK ...`, `SIGN_OK ...`, `SIGN_SKIPPED ...`
**Apply to:** `tools/linux-flatpak/build.sh`

Same prefix convention. CI and wrapper scripts grep these tokens; keeping consistent naming across AppImage and Flatpak builds is important.

### Drift-guard Fixture Shape (file-read + assertion)
**Source:** `tests/test_packaging_linux_spec.py` lines 43–79
**Apply to:** New Flatpak section in `tests/test_packaging_spec.py`

Pattern: `Path(__file__).resolve().parent.parent / ...`, `scope="module"` fixture, `assert file.is_file()`, `.read_text(encoding="utf-8")`. For YAML guards, add `yaml.safe_load()` as the parser. For shell guards, use `_strip_comments_sh()` before negative assertions.

### Pure-module, No-Qt Pattern
**Source:** `musicstreamer/paths.py` (entire file)
**Apply to:** `musicstreamer/flatpak_first_launch.py`

Keep the module pure (no Qt imports, no side effects at import time, no filesystem writes). Detection logic returns booleans; the UI caller (wizard) calls it. Mirrors `paths.py`'s design intent (lines 1–15 docstring).

### `_validate_zip_members` Security Re-validation
**Source:** `musicstreamer/settings_export.py` lines 73–100
**Apply to:** `musicstreamer/flatpak_first_launch.py` (import flow)

The import flow calls `preview_import` + `commit_import` — both already call `_validate_zip_members` internally (RESEARCH.md Security §V5). No additional call needed; this is documented here so implementer does not accidentally bypass the existing security gate by calling only the raw ZIP extraction path.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` | config | — | First AppStream metainfo file in the project; no XML analog exists |

---

## Critical Implementation Notes for Planner

1. **`flatpak build-bundle` signing is inline** — unlike the AppImage's `gpg --detach-sign` sidecar, `flatpak build-bundle --gpg-sign` embeds the signature inside the `.flatpak` bundle itself. There is no `.flatpak.sig` artifact to upload separately. The drift-guard for signing therefore checks for `--gpg-sign` in `build.sh` source text, not for a `.sig` file presence.

2. **Deny-list is the security-critical half** (D-13 / `feedback_drift_guard_presence_not_semantics`) — `test_flatpak_finish_args_deny_list` is the more important test. Parse YAML as data (`yaml.safe_load`), not text grep. A permission added in a YAML comment would pass a text check.

3. **`flatpak-requirements.txt` must exclude `PySide6`** — the curated exclusion list is the mechanism that prevents Pitfall 5 (PySide6 double-install). It is a separate checked-in file under `tools/linux-flatpak/`, not an inline list in `build.sh`.

4. **node20 copy step is in the manifest, not build.sh** — `install -D /usr/lib/sdk/node20/bin/node /app/bin/node` belongs in `io.github.kcreasey.MusicStreamer.yaml`'s `build-commands`, not in `build.sh`. The `runtime_check.check_node()` / `yt_dlp_opts.build_js_runtimes()` code paths are unchanged; they call `shutil.which("node")` which finds `/app/bin/node` inside the sandbox.

5. **XDG_DATA_HOME remapping is automatic** — `paths.data_dir()` inside the sandbox already returns the correct sandbox path (`~/.var/app/.../data/musicstreamer`) because Flatpak overrides `XDG_DATA_HOME`. The `flatpak_first_launch.py` module must use a LITERAL `os.path.expanduser("~/.local/share/musicstreamer")` constant for the host detection — never `paths.db_path()`.

---

## Metadata

**Analog search scope:** `tools/linux-build/`, `.github/workflows/`, `tests/test_packaging_*.py`, `musicstreamer/paths.py`, `musicstreamer/settings_export.py`, `musicstreamer/ui_qt/settings_import_dialog.py`, `musicstreamer/runtime_check.py`, `musicstreamer/yt_dlp_opts.py`
**Files scanned:** 10
**Pattern extraction date:** 2026-06-02
