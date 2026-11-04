# One click: makes sure Ollama is running, starts Otto's server (detached, see server.ps1) if it is not already up, then opens the page in the default browser.
# The access token is never put in the address: the browser remembers it from the first time you opened the page with ?token=... (about 30 days).
param([switch]$Quiet)

Add-Type -AssemblyName PresentationFramework
$root = Split-Path -Parent $PSScriptRoot
$port = 8765
$listening = { param($p) [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }
function Fail($msg) { [System.Windows.MessageBox]::Show($msg, "Otto Pilot", "OK", "Warning") | Out-Null; exit 1 }

if (-not (& $listening 11434)) {                                   # the model server
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) { Fail "Ollama is not running and could not be found. Start Ollama first." }
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 20 -and -not (& $listening 11434); $i++) { Start-Sleep 1 }
}

if (-not (& $listening $port)) {
    & (Join-Path $PSScriptRoot "server.ps1") start | Out-Null
    if (-not (& $listening $port)) { Fail "Otto's server did not start. Look at data\server.log in the project folder." }
}

$ip = (& tailscale ip -4 2>$null | Select-Object -First 1)         # the server listens on the Tailscale address
if (-not $ip) {
    $line = Get-Content (Join-Path $root "data\server.log") -ErrorAction SilentlyContinue | Where-Object { $_ -match "will be at\s+http://(\S+?)/" } | Select-Object -Last 1
    if ($line -match "http://(\S+?)/") { $ip = $Matches[1] -replace ":\d+$", "" }
}
if (-not $ip) { $ip = "127.0.0.1" }
Start-Process "http://${ip}:${port}/"
