# Phase 43 Spike Runbook

Throwaway experiment: validate HTTPS GStreamer playback inside a PyInstaller `--onedir` bundle on a clean Windows 11 VM. Produces `43-SPIKE-FINDINGS.md` + a draft `.spec` for Phase 44 to inherit.

## One-time VM setup

1. Revert the Win11 VM to a clean snapshot (no system GStreamer on PATH — D-01).
2. Download `gstreamer-1.0-msvc-x86_64-1.28.2.exe` (~500 MB) from
   https://gstreamer.freedesktop.org/data/pkg/windows/1.28.2/msvc/
   and install it with the **Complete** feature set to `C:\spike-gst\runtime\`.
   (Complete ensures `libgiognutls.dll` and `gst-plugin-scanner.exe` land — both required.)
   Post-install sanity: `C:\spike-gst\runtime\bin\` must contain
   `libgstreamer-1.0-0.dll` and `gst-inspect-1.0.exe`.
   (1.28.x uses a flat tree — no `\1.0\msvc_x86_64\` subdir, unlike 1.24/1.26.)
3. Ensure Python 3.10+ is on PATH (`python --version`).
4. Copy this phase directory to the VM (or clone the repo on the VM).
5. Populate `test_url.txt` with one AA HTTPS channel URL from the user's library (contains live listen key — gitignored).

## Per-iteration loop

1. `cd` into this phase directory on the VM.
2. Run `.\build.ps1` — builds the bundle via PyInstaller, then runs `smoke_test.py` against the test URL.
3. Paste the full content of `artifacts\smoke.log` back into the chat.
4. After pasting, state one word: `audible` or `silent` (whether speakers produced sound).
5. Claude diffs the log, updates `43-spike.spec` or `runtime_hook.py`, commits, and you re-run step 2.

## Pass conditions

Spike passes when a single iteration produces:
- `SPIKE_OK audio_sample_received=True` in `smoke.log`
- `SPIKE_DIAG ... has_default_database=True` in `smoke.log` (proves `libgiognutls.dll` loaded)
- You reply `audible` (optional — `silent` with `SPIKE_OK` still counts, logs a VM audio note)

Then Claude runs `/gsd-spike-wrap-up` to persist findings. ≤5 iteration budget before scope revisit.

## Never commit

`test_url.txt`, `artifacts/`, `build/`, `dist/` — all in `.gitignore`.
