#!/usr/bin/env bash
# Phase 61 Plan 05 dev launcher.
#
# Wraps the dev-venv musicstreamer invocation in a transient systemd user
# scope named after our app id, so mutter's cgroup-based window↔.desktop
# matching works for terminal-launched dev runs.
#
# Without this wrapper, terminal launches inherit the parent terminal's
# systemd scope (e.g., app-org.gnome.Terminal-<id>.scope or
# app-gnome-jetbrains-pycharm-<id>.scope when running inside a JetBrains IDE
# terminal). Mutter parses the *parent's* app id out of that cgroup name and
# attributes our new window to the parent app — producing the BUG-08 symptom
# (gear icon + raw app_id in the dock and force-quit dialog) for terminal
# launches even after Plans 02 + 03 fixed the .desktop and wayland app_id.
#
# End-user launches via the Activities overview / dock / .desktop file
# already get a properly-named scope from gnome-shell's launcher, so this
# wrapper only matters for development. It replaces the older one-line
# `run_local.sh` (`uv run python -m musicstreamer`).
#
# Cgroup unit-name format is the freedesktop systemd-app convention:
#   app-<reverse-dns>-<token>.scope
# Mutter's parser splits on the LAST `-` to separate <reverse-dns> from
# <token>. We use `$$` (this shell's PID) as the token — unique within the
# user's session, simple, no dash to confuse the parser.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Mirror of musicstreamer/constants.py::APP_ID. Drift-guarded by
# tests/test_constants_drift.py::test_dev_launch_script_app_id_matches_constants.
APP_ID="org.lightningjim.MusicStreamer"

VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "dev-launch: $VENV_PYTHON not found. Run 'uv sync' first." >&2
  exit 1
fi

if ! command -v systemd-run >/dev/null 2>&1; then
  echo "dev-launch: systemd-run not on PATH. This wrapper only works on systemd-managed Linux." >&2
  exit 1
fi

# Feature-probe: --collect was added in systemd v236 (Dec 2017). Older
# releases (Debian 9 / RHEL 7) silently misinterpret the flag. Fail fast
# with a clear message rather than letting systemd-run dump a generic
# usage error. (Code review WR-04.)
if ! systemd-run --user --scope --collect --help 2>&1 | grep -q -- '--collect'; then
  echo "dev-launch: systemd-run lacks --collect (need systemd 236+)" >&2
  exit 1
fi

# --user: place the scope under our user systemd instance (no root needed)
# --scope: transient scope unit; process tree stays attached, no service unit
# --quiet: suppress systemd's "Running as unit:" preamble
# --collect: drop the unit when the process exits (no leftover failed units)
exec systemd-run --user --scope --quiet --collect \
  --unit="app-${APP_ID}-$$.scope" \
  -- "$VENV_PYTHON" -m musicstreamer "$@"
