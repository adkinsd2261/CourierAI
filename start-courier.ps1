param([switch]$Rebuild, [ValidateRange(1024, 65535)][int]$DashboardPort = 3000)
$ErrorActionPreference = 'Stop'
$courierRoot = $PSScriptRoot
Set-Location -LiteralPath $courierRoot
$courierPython = Join-Path $courierRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $courierPython)) { throw 'Create .venv and install requirements first. See README.md.' }
$courierNode = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $courierNode) {
    $courierNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
if (-not (Test-Path -LiteralPath $courierNode)) { throw 'Install Node.js 20.9 or later.' }
$env:PATH = (Split-Path $courierPython) + ';' + (Split-Path $courierNode) + ';' + $env:PATH
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:COURIER_DASHBOARD_PORT = [string]$DashboardPort
& $courierPython scripts\prepare_ffmpeg.py
if ($LASTEXITCODE -ne 0) { throw 'ffmpeg setup failed. Install requirements or add ffmpeg to PATH.' }
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
$courierNext = Join-Path $courierRoot 'frontend\node_modules\next\dist\bin\next'
if (-not (Test-Path -LiteralPath $courierNext)) { throw 'Install frontend dependencies first. See README.md.' }
Push-Location (Join-Path $courierRoot 'frontend')
try {
    if ($Rebuild -or -not (Test-Path -LiteralPath '.next\BUILD_ID')) {
        & $courierNode $courierNext build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
} finally { Pop-Location }
# Refuse occupied ports; never stop an unrelated application to claim a port.
foreach ($courierPort in @(8000, $DashboardPort)) {
    $courierProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $courierPort)
    try { $courierProbe.Start() } catch { throw "Port $courierPort is already in use. Stop the existing instance first." }
    finally { $courierProbe.Stop() }
}
$courierLogDir = Join-Path $courierRoot 'logs'
New-Item -ItemType Directory -Force -Path $courierLogDir | Out-Null
$courierBackend = $null
$courierFrontend = $null
try {
    $courierBackend = Start-Process -FilePath $courierPython -ArgumentList @('-m', 'backend.main') -WorkingDirectory $courierRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $courierLogDir 'backend.stdout.log') -RedirectStandardError (Join-Path $courierLogDir 'backend.stderr.log')
    $courierFrontend = Start-Process -FilePath $courierNode -ArgumentList @(('"' + $courierNext + '"'), 'start', '--hostname', '127.0.0.1', '--port', [string]$DashboardPort) -WorkingDirectory (Join-Path $courierRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $courierLogDir 'frontend.stdout.log') -RedirectStandardError (Join-Path $courierLogDir 'frontend.stderr.log')
    Write-Host "CourierAI: http://localhost:$DashboardPort"
    Write-Host 'Select the game, press Start, then click the game window. F12 is Emergency Stop.'
    Write-Host 'Keep this terminal open. Stop the agent in the dashboard before closing it.'
    while (-not $courierBackend.HasExited -and -not $courierFrontend.HasExited) { Start-Sleep -Seconds 1 }
    Write-Host 'A service exited. See logs/backend.stderr.log and logs/frontend.stderr.log.'
} finally {
    if ($courierBackend -and -not $courierBackend.HasExited) { & $courierPython scripts\shutdown.py }
    # Only processes created by this launcher; no tree-wide or name-based termination.
    if ($courierBackend -and -not $courierBackend.HasExited) { Stop-Process -InputObject $courierBackend }
    if ($courierFrontend -and -not $courierFrontend.HasExited) { Stop-Process -InputObject $courierFrontend }
}
