# Starts, stops or restarts Otto's server so that it runs ON ITS OWN: the process is created through Windows' process service (WMI),
# so it is not a child of whatever started this script (a terminal, an editor session or an assistant session) and keeps running when that goes away.
#   powershell -File tools\server.ps1 start      start it (does nothing if it is already listening)
#   powershell -File tools\server.ps1 stop       the clean stop: writes the KILL file and waits for the port to close
#   powershell -File tools\server.ps1 restart    stop, then start
# The access token is read from the Windows user variable SPROCKET_TOKEN inside the new process; it never appears on a command line.
# Output goes to data\server.log (UTF-16 as PowerShell writes it; read it with Get-Content).
param([Parameter(Position = 0)][ValidateSet("start", "stop", "restart")][string]$Action = "restart")

$root = Split-Path -Parent $PSScriptRoot
$port = 8765
$kill = Join-Path $root "KILL"
$log = Join-Path $root "data\server.log"
$listening = { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }

function Stop-Otto {
    if (-not (& $listening)) { Write-Host "not running"; return }
    New-Item -ItemType File -Path $kill -Force | Out-Null
    for ($i = 0; $i -lt 60 -and (& $listening); $i++) { Start-Sleep 1 }
    Start-Sleep 2
    if (Test-Path $kill) { Remove-Item $kill -Force }
    Write-Host ("stopped: " + (-not (& $listening)))
}

function Start-Otto {
    if (& $listening) { Write-Host "already running"; return }
    if (Test-Path $kill) { Remove-Item $kill -Force }
    $inner = "Set-Location '$root'; `$env:SPROCKET_TOKEN=[Environment]::GetEnvironmentVariable('SPROCKET_TOKEN','User'); cmd /c start-otto-pc.bat *> '$log'"
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "powershell.exe -NoProfile -WindowStyle Hidden -Command `"$inner`""; CurrentDirectory = $root }
    if ($r.ReturnValue -ne 0) { Write-Host "could not start (code $($r.ReturnValue))"; exit 1 }
    for ($i = 0; $i -lt 90 -and -not (& $listening); $i++) { Start-Sleep 2 }
    Write-Host ("running: " + (& $listening))
}

switch ($Action) {
    "start" { Start-Otto }
    "stop" { Stop-Otto }
    "restart" { Stop-Otto; Start-Otto }
}
