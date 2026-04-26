# Phase 44: Windows Packaging + Installer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 44-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 44-windows-packaging-installer
**Areas discussed:** Installer tool + structure, Single-instance (PKG-04) + Node.js UX, Smoke-test checklist + DI.fm HTTPS policy, Scope edges (Linux + plugin pruning)

---

## Installer Tool + Structure

### Q: Which installer tool?
| Option | Description | Selected |
|--------|-------------|----------|
| Inno Setup (Recommended) | Simpler Pascal-style scripting. First-class per-user install mode. Built-in shortcut properties support AUMID. | ✓ |
| NSIS | Mentioned first in ROADMAP. More flexible but more verbose. Per-user install needs more wiring. AUMID shortcut requires a plugin. | |

**User's choice:** Inno Setup

### Q: Upgrade behavior when installing over an existing version?
| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite existing install (Recommended) | Detect prior install via registry, remove old files, install new. User data in separate dir, untouched. | ✓ |
| Block with "uninstall first" prompt | Safer but more friction. | |
| Side-by-side versions | Overkill for a personal project. | |

**User's choice:** Overwrite existing install

### Q: Which shortcuts does the installer create?
| Option | Description | Selected |
|--------|-------------|----------|
| Start Menu (Required) | Mandatory — carries the AUMID so SMTC shows 'MusicStreamer' instead of 'Unknown app'. | ✓ |
| Desktop shortcut (optional at install-time) | Checkbox on Tasks page, user-selectable. | |
| Pin to Taskbar | Requires a script hack on modern Windows; fragile. | (initially selected, then dropped) |

**User's choice:** Start Menu only. User explicitly revised to drop Pin-to-Taskbar: "We can drop the pin to taskbar requirement. Windows users can always do it after they launch the program."
**Notes:** Desktop shortcut not requested. Taskbar pin left as a user-manual step post-install.

### Q: Include a license page in the installer?
| Option | Description | Selected |
|--------|-------------|----------|
| No license page (Recommended) | Repo has no LICENSE file. Personal-scale app. | |
| Add a short EULA/notice page | Requires writing minimal notice text (personal use, GStreamer LGPL, etc.). | ✓ |

**User's choice:** Add a short EULA/notice page
**Notes:** EULA content to be drafted during planning; covers personal use, no warranty, GStreamer LGPL, yt-dlp/streamlink attribution.

---

## Single-Instance (PKG-04) + Node.js UX

### Q: Single-instance mechanism?
| Option | Description | Selected |
|--------|-------------|----------|
| QLocalServer/QLocalSocket (Recommended) | Qt-native. Cross-platform. Second instance sends 'activate', first raises window. | ✓ |
| QLockFile + Windows named mutex | Simpler: detect 'already running' and exit silently. No window-raise. | |
| You decide | Defer to planner. | |

**User's choice:** QLocalServer/QLocalSocket

### Q: When user double-clicks app while already running, what happens?
| Option | Description | Selected |
|--------|-------------|----------|
| Raise + focus existing window (Recommended) | Restore from minimize, `raise_()` + `activateWindow()`, FlashWindow fallback. | ✓ |
| Raise window + flash taskbar icon | Same plus taskbar flash. | |
| Silent exit | Second instance just exits. | |

**User's choice:** Raise + focus existing window

### Q: Behavior when Node.js is missing from PATH at startup?
| Option | Description | Selected |
|--------|-------------|----------|
| Soft warning dialog + continue (Recommended) | Non-blocking QMessageBox. App continues — ShoutCast/HLS/Twitch all work. | ✓ |
| Blocking dialog — exit if declined | Hard stop; blocks even users who never use YouTube. | |
| Silent (no startup check) | yt-dlp fails with cryptic error at YT play time. | |

**User's choice:** Soft warning dialog + continue

### Q: Where should the Node.js-missing warning surface?
| Option | Description | Selected |
|--------|-------------|----------|
| Startup dialog (once per missing-state session) | On app launch, if Node.js absent, show warning dialog immediately. | ✓ |
| Toast at YT play time | When user tries to play YT and yt-dlp fails, show toast with nodejs.org link. | ✓ |
| Persistent indicator in hamburger menu | 'Node.js: Missing' entry in hamburger menu while absent. | ✓ |

**User's choice:** All three — three-pronged surfacing.

---

## Smoke-Test Checklist + DI.fm HTTPS Policy

### Q: DI.fm HTTPS policy (spike gotcha #6)?
| Option | Description | Selected |
|--------|-------------|----------|
| Accept as server-side issue (Recommended) | SomaFM HTTPS proves TLS works. Document, no code change. | ✓ |
| Per-provider HTTP rewrite on AA import | Rewrite DI.fm URLs `https://` → `http://` at import time. | |
| Per-URL HTTPS→HTTP fallback in player.py | Auto-retry HTTP on stream error -5. Adds complexity. | |

**User's choice:** Accept as server-side issue

### Q: Smoke test — playback/feature items to verify
| Option | Description | Selected |
|--------|-------------|----------|
| Core streams: SomaFM HTTPS + HLS + DI.fm HTTP (Recommended) | Three codec/transport families validated. | ✓ |
| YouTube live w/ Node.js + w/o Node.js (Recommended) | With: LoFi Girl plays. Without: warning surfaces, non-YT streams still work. | ✓ |
| Twitch via streamlink + OAuth (Recommended) | Live Twitch stream plays. | ✓ |
| Multi-stream failover + SMTC round-trip (Recommended) | Failover picks next stream. Windows media keys + SMTC overlay show station/ICY/art. | ✓ |

**User's choice:** All four selected.

### Q: Smoke test — installer/round-trip items
| Option | Description | Selected |
|--------|-------------|----------|
| Installer round-trip (Recommended) | Fresh VM: installer → Start Menu → uninstall clean → re-install. | ✓ |
| Settings export Linux↔Windows (Recommended — SC-6) | Export on one OS, import on other; verify round-trip. | ✓ |
| Single-instance activation (Recommended) | Double-click shortcut while running → existing window raises. | ✓ |
| AUMID / SMTC app-name shows 'MusicStreamer' | Start Menu shortcut AUMID makes SMTC show app name correctly. | ✓ |

**User's choice:** All four selected.

### Q: How often is the smoke test run?
| Option | Description | Selected |
|--------|-------------|----------|
| Once per phase-44 ship (Recommended) | Manual UAT on clean Win11 VM when installer is ready. | ✓ |
| Also after any packaging-critical change | Re-run on any `.spec`/rthook/`build.ps1`/installer change. | |
| CI-automated on every commit | GitHub Actions Windows runner; high investment. | |

**User's choice:** Once per phase-44 ship

---

## Scope Edges (Linux + Plugin Pruning)

### Q: Does Phase 44 produce a Linux artifact, or strictly Windows?
| Option | Description | Selected |
|--------|-------------|----------|
| Strictly Windows (Recommended) | Linux users keep `pip install .` / existing wheel. No new Linux artifact. | ✓ |
| Windows + refreshed Linux wheel upload | Also build v2.0 wheel + sdist via `python -m build`. | |
| Windows + AppImage/Flatpak scaffold | Full cross-platform packaging; significant scope creep. | |

**User's choice:** Strictly Windows

### Q: GStreamer plugin pruning approach?
| Option | Description | Selected |
|--------|-------------|----------|
| Broad-collect all 184 plugins (~110 MB) (Recommended) | Ship everything Phase 43 validated. Known-good. | ✓ |
| Aggressive prune in-phase | Exclude gtk*/cuda*/vulkan*/vaapi*/webrtc* etc. ~50-70 MB bundle. | |
| Conservative prune (low-risk exclusions only) | Only gtk*/qt5*/nv*/vulkan/d3d11*/vaapi*. ~20-30 MB savings. | |

**User's choice:** Broad-collect all 184 plugins

### Q: PKG-03 (_popen) compliance — current state zero subprocess callers. How to handle?
| Option | Description | Selected |
|--------|-------------|----------|
| Retire PKG-03 as no-op ship-time check (Recommended) | Add ripgrep guard in build.ps1; keep `_popen` helper. | ✓ |
| Also add a runtime guard | Monkey-patch `subprocess.Popen` to warn at runtime. | |
| Nothing — PKG-03 is retired | Drop requirement entirely; rely on review. | |

**User's choice:** Retire PKG-03 as no-op ship-time check

### Q: QA-05 widget lifetime audit — what's the deliverable?
| Option | Description | Selected |
|--------|-------------|----------|
| Document-only audit + spot fixes (Recommended) | Grep QWidget subclasses + dialog open paths; fix findings; write 44-QA05-AUDIT.md. | ✓ |
| Add a pytest-qt stress test | Open/close every dialog 20x; assert no RuntimeError. | |
| Skip QA-05 for this phase, punt to backlog | No audit. | |

**User's choice:** Document-only audit + spot fixes

---

## Wrap-up

### Q: Anything else to discuss, or ready to write CONTEXT.md?
| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context (Recommended) | Lock decisions, write CONTEXT.md, auto-chain to plan-phase. | |
| Version bump + EULA content | Decide: bump pyproject to 2.0.0? What EULA text? | |
| Explore more gray areas | Icon formats, build artifact git strategy, Node.js doc communication. | |

**User's choice (Other):** "We can drop the pin to taskbar requirement. Windows users can always do it after the launch the program."
**Notes:** This retroactively revises the shortcut decision: Start Menu only (mandatory, carries AUMID); no Pin-to-Taskbar. Version bump to 2.0.0 folded into CONTEXT D-06 as Claude's Discretion with EULA content deferred to planning.

---

## Claude's Discretion (noted in CONTEXT.md)

- Exact GUID for Inno Setup `AppId` — generate once, lock into `.iss`
- EULA wording — draft per intent in D-05; user reviews final copy
- Naming of single-instance helper module (e.g., `musicstreamer/single_instance.py`)
- Whether Node.js startup check + warning live in `__main__.py` or dedicated `musicstreamer/runtime_check.py`
- Location of `packaging/` directory relative to repo root (assumed `packaging/windows/`)

## Deferred Ideas

- Code signing / MSIX / auto-update — v2.1+
- AppImage / Flatpak — v2.1+
- GitHub Actions Windows CI — v2.1+
- Aggressive GStreamer plugin pruning — revisit if bundle size becomes an issue
- Audio pause/restart glitch on Windows (GStreamer, not SMTC) — STATE.md blocker list
- `test_thumbnail_from_in_memory_stream` `MagicMock` → `AsyncMock` — STATE.md blocker list
