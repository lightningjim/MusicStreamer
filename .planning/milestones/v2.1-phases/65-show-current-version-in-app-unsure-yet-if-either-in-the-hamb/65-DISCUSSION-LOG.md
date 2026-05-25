# Phase 65: Show current version in app - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
**Areas discussed:** Placement, Version source at runtime, Display format, Click behavior

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Placement | Hamburger menu vs menubar right corner vs About dialog vs multiple. | ✓ |
| Version source at runtime | __version__.py vs importlib.metadata vs pyproject.toml parse. | ✓ |
| Display format | 'v2.1.63' vs '2.1.63' vs full app-name vs with milestone codename. | ✓ |
| Click behavior | Disabled vs copy-to-clipboard vs About dialog vs GitHub release URL. | ✓ |

**User's choice:** All four areas selected (multiSelect).

---

## Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Hamburger menu footer | Disabled QAction at the bottom of the hamburger menu. Discoverable when opened; no always-visible UI cost. | ✓ |
| Menubar right-corner label | QLabel set as menubar corner widget (right side, opposite the hamburger). Always visible. | |
| Both | Always-visible corner label + richer hamburger entry. Glance + deep-dive. | |

**User's choice:** Hamburger menu footer.
**Notes:** Single discoverable surface preferred over always-visible header real estate. Menubar corner widget explicitly declined.

---

## Version source at runtime

### Q1 — Read mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| importlib.metadata | Reads from installed package metadata; auto-stays-in-sync with pyproject.toml. Works in dev and (with --copy-metadata) in PyInstaller bundle. | ✓ |
| Refresh __version__.py automatically | Extend Phase 63's bump hook to also rewrite __version__.py per phase. Second mutation per bump. | |
| Parse pyproject.toml at runtime | tomllib.load on pyproject.toml. Simple in dev, awkward in bundle. | |

**User's choice:** importlib.metadata.

### Q2 — Disposition of stale __version__.py

| Option | Description | Selected |
|--------|-------------|----------|
| Delete it | Remove __version__.py outright. Single source = pyproject.toml. | ✓ |
| Replace with importlib.metadata wrapper | Keep module name; rewrite body to `__version__ = version("musicstreamer")`. | |
| Keep as build-time fallback | Bump hook rewrites it; runtime falls back when PackageNotFoundError. | |

**User's choice:** Delete it.
**Notes:** build.ps1 reads version from pyproject.toml directly via regex (verified at packaging/windows/build.ps1:141-148), so deletion is safe. A pre-deletion grep gate validates zero remaining importers (D-06a).

### Q3 — Qt setApplicationVersion

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, set it from importlib.metadata | Add `app.setApplicationVersion(...)` next to setApplicationName/setApplicationDisplayName. Idiomatic Qt. | ✓ |
| No, just read where displayed | Single read site at the menu construction. Narrow surface. | |

**User's choice:** Yes — set Qt's applicationVersion.
**Notes:** Lets QCoreApplication.applicationVersion() serve as the in-app read site without re-importing metadata.

### Q4 — PyInstaller bundle handling

| Option | Description | Selected |
|--------|-------------|----------|
| Add --copy-metadata flag to build | Update spec/build to include musicstreamer's dist-info. Smoke test guards regression. | ✓ |
| Try/except fallback to '0.0.0-dev' | Wrap call so PackageNotFoundError yields placeholder. Defeats feature on Win11 rig. | |
| Both — add --copy-metadata AND fallback | Belt-and-suspenders. Slightly more code. | |

**User's choice:** Add --copy-metadata.
**Notes:** Mechanism = `copy_metadata("musicstreamer")` in MusicStreamer.spec datas concatenation, mirroring the existing collect_all pattern for charset_normalizer / streamlink / yt_dlp.

---

## Display format

| Option | Description | Selected |
|--------|-------------|----------|
| Version 2.1.63 | Plain prefix + raw version. | |
| v2.1.63 | Compact 'v' + version. | ✓ |
| MusicStreamer 2.1.63 | App name + version. Redundant inside MusicStreamer's own menu. | |
| MusicStreamer v2.1.63 (v2.1 Fixes & Tweaks) | Version + milestone codename from PROJECT.md. | |

**User's choice:** v2.1.63.
**Notes:** Compact format reads cleanly in a menu footer. No styling beyond Qt's default disabled-action grey.

---

## Click behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Disabled — not clickable | QAction.setEnabled(False). Pure informational footer. | ✓ |
| Click copies to clipboard | Copy version string + show toast. Useful for bug reports. | |
| Click opens About dialog | Adds About MusicStreamer… modal (license/repo/Qt version/etc). Bigger surface. | |
| Click opens GitHub release page | QDesktopServices.openUrl to releases/tag/v2.1.63. Requires release tags that don't exist. | |

**User's choice:** Disabled — not clickable.

---

## Claude's Discretion

- Exact action variable name (`self._act_version` recommended, planner picks).
- Whether to read via `QCoreApplication.applicationVersion()` (Qt slot) or `importlib.metadata.version("musicstreamer")` directly at the menu site.
- Whether to introduce a small helper module (`musicstreamer/version.py`) or read inline at both setup and display sites.
- Test placement (extend `tests/test_main_window.py` vs new `tests/test_version.py` vs fold into existing module).
- Whether `copy_metadata("musicstreamer")` lives next to the existing `collect_all` block or wraps into the existing concatenation.
- `addAction(label).setEnabled(False)` vs `addSection(label)` for the visual treatment.
- Whether to keep the `v(unknown)` defensive-fallback for empty `applicationVersion()` (D-11).

---

## Deferred Ideas

- About MusicStreamer… dialog (license, repo URL, Qt/PySide6 version, copyright, optional build SHA).
- Click-to-copy clipboard with toast.
- Click-to-open GitHub release page (depends on release tags not existing today).
- Menubar right-corner label — declined in favor of menu footer.
- Milestone codename in the label — declined for compactness.
- CLI `--version` flag (`python -m musicstreamer --version`).
- Build-SHA / dirty-flag in the version string.
- Self-healing `__version__.py` — rejected; file is being deleted.
- Auto-tagging git releases on phase completion (carried from Phase 63's deferred list).

