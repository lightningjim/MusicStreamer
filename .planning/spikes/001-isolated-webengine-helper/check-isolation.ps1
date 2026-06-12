# Spike 001 Stage C - isolation-under-contention check. ASCII ONLY.
#
# Proves the B1 safety property: the frozen helper exe loads its OWN bundled Qt
# by adjacency EVEN WHEN conda's qt6-main (Library\bin) is on PATH - which is
# exactly the environment the main conda exe would spawn it in. If adjacency
# did NOT win, this run would reproduce the Phase 88.3 G6 DLL-load failure.
#
# Run on the VM from this spike dir AFTER build-helper.ps1 succeeded:
#   powershell -ExecutionPolicy Bypass -File .\check-isolation.ps1 -CondaBin "C:\Users\you\miniforge3\envs\musicstreamer-build\Library\bin"
#
# Exit codes:
#   0  helper STILL loaded its own Qt + probe passed with conda on PATH (B1 safe)
#   30 -CondaBin path not found
#   31 probe failed with conda on PATH (adjacency did NOT win - B1 needs a fix)

param(
    [Parameter(Mandatory = $true)]
    [string]$CondaBin
)

$ErrorActionPreference = "Stop"
function Invoke-Native { param([scriptblock]$b) $p=$ErrorActionPreference; $ErrorActionPreference="Continue"; try { & $b } finally { $ErrorActionPreference=$p } }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path $CondaBin)) {
    Write-Host "Conda Library\bin not found: $CondaBin" -ForegroundColor Red
    Write-Host "Find it with:  conda activate musicstreamer-build; where.exe Qt6Core.dll" -ForegroundColor Yellow
    exit 30
}

$smokeExe = Join-Path $ScriptDir "dist\webengine_smoke\webengine_smoke.exe"
if (-not (Test-Path $smokeExe)) {
    Write-Host "Smoke exe not built - run build-helper.ps1 first" -ForegroundColor Red
    exit 31
}

# Confirm the contamination is real: conda's Qt6Core must be the one PATH resolves.
Write-Host "PREPENDING conda Library\bin to PATH (simulating launch-from-conda-exe):" -ForegroundColor Cyan
Write-Host "  $CondaBin" -ForegroundColor Cyan
$env:PATH = "$CondaBin;$env:PATH"
$whereQt = (Invoke-Native { where.exe Qt6Core.dll 2>&1 }) -join "`n"
Write-Host "where.exe Qt6Core.dll  ->" -ForegroundColor Cyan
Write-Host $whereQt
if ($whereQt -notmatch [regex]::Escape($CondaBin)) {
    Write-Host "NOTE: conda Qt6Core not first on PATH - contamination may be weaker than the real spawn." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Launching the frozen smoke WITH conda Qt on PATH (probe mode) ..." -ForegroundColor Cyan
Invoke-Native { & $smokeExe --probe --url "https://example.com" --timeout 25 *>&1 | Tee-Object "isolation-probe.log" }
$code = $LASTEXITCODE
Write-Host ""
Write-Host "Isolation probe exit code: $code" -ForegroundColor Cyan
Write-Host "(Inspect isolation-probe.log: the 'path_audit' event should show conda entries," -ForegroundColor Cyan
Write-Host " AND 'qt_exec_path' should point INTO the bundle's _MEIPASS\PySide6, NOT conda.)" -ForegroundColor Cyan

if ($code -ne 0) {
    Write-Host "STAGE C FAIL: bundled Qt did NOT win over conda PATH (B1 needs explicit isolation)." -ForegroundColor Red
    exit 31
}
Write-Host "STAGE C PASS: adjacency won; helper exe is safe to spawn from the conda main exe." -ForegroundColor Green
exit 0
