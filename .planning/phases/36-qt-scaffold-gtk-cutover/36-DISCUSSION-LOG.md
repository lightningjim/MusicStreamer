# Phase 36: Qt Scaffold + GTK Cutover - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 36-qt-scaffold-gtk-cutover
**Areas discussed:** Bare-window scope, Entry point strategy, Icon sourcing, Icon scope, Dead-code cleanup
**User response:** "defaults"

---

## Gray Areas

### 1. Bare-window scope

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Truly empty | `QMainWindow` with only `setWindowTitle("MusicStreamer")` — Phase 37 creates menubar, central widget, status bar | |
| (b) Structural containers | Include empty menubar, central widget, status bar now so Phase 37 just populates them (recommended default) | ✓ |
| (c) Structural + menu actions | Include containers AND wire hamburger menu entries as no-op `QAction`s (UI-10 partial) | |

**User's choice:** defaults → (b)
**Rationale:** Smoother Phase 37 work — no shell refactoring when content arrives.

### 2. Entry point strategy

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Replace `__main__.py` entirely | Delete Phase 35 headless smoke path; `python -m musicstreamer` only opens window | |
| (b) CLI flag | `python -m musicstreamer` opens window; `--smoke <url>` runs Phase 35 headless harness (recommended default) | ✓ |
| (c) Split into two files | `__main__.py` = GUI; `_smoke.py` = headless | |

**User's choice:** defaults → (b)
**Rationale:** Preserves backend smoke-test capability cheaply via argparse flag.

### 3. Icon sourcing

| Option | Description | Selected |
|--------|-------------|----------|
| (a) GNOME Adwaita SVGs | Extract from adwaita-icon-theme (CC-BY-SA 3.0), preserves v1.5 icon names for theme fallback (recommended default) | ✓ |
| (b) Material Design Icons / Tabler | Independent icon set, different aesthetic | |
| (c) Hand-rolled minimal SVGs | Most work, full license freedom | |

**User's choice:** defaults → (a)
**Rationale:** Icon name continuity with v1.5 enables `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback to succeed on Linux via system theme AND Windows via bundled SVG.

### 4. Icon scope in Phase 36

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Minimal | Ship only icons Phase 36's bare window needs (1–2 SVGs); later phases add more (recommended default) | ✓ |
| (b) Full set upfront | Ship all ~15 v1.5 icons even though Phase 36 doesn't display them | |

**User's choice:** defaults → (a)
**Rationale:** Phase 36's bare window has almost no icon surface; later phases ship icons as they need them.

### 5. Dead-code cleanup — `mpris.py` and `dbus-python` dep

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Keep stub + dep | `mpris.py` and `dbus-python` stay on disk for Phase 41 to overwrite | |
| (b) Delete both now | Phase 41 recreates both as QtDBus; clean interim dep graph (recommended default) | ✓ |
| (c) Shrink stub + drop dep | Stub shrinks to 5-line placeholder, dep drops | |

**User's choice:** defaults → (b)
**Rationale:** No callers remain after `main_window.py` deletion; Phase 41 starts fresh with QtDBus.

---

## Claude's Discretion

- `QVBoxLayout` spacing/margins for empty central widget
- `QMainWindow` subclass vs direct use (recommend subclass)
- Exact menubar placeholder implementation
- `argparse` formatter class
- `icons_rc.py` gitignored vs committed
- Exact list of Adwaita SVGs extracted

## Deferred Ideas

- Window geometry persistence via `QSettings` → future QoL phase or Phase 40
- Accent color palette integration → Phase 40 (UI-11)
- Hamburger menu actions wired → Phase 40 (UI-10)
- Station list UI → Phase 37 (UI-01)
- Now-playing panel UI → Phase 37 (UI-02)
- Toast overlay widget → Phase 37 (UI-12)
- Full icon inventory → rolled in as later phases need icons
- Real MPRIS2 implementation → Phase 41 (MEDIA-02)
- Windows packaging → Phase 44
</content>
</invoke>
