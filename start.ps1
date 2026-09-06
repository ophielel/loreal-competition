param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    Write-Host 'Python 3.11+ is required. Install Python, then run this script again.'
    exit 1
}
$DemoUrl = "http://127.0.0.1:$Port"
try {
    $Existing = Invoke-RestMethod "$DemoUrl/api/overview" -TimeoutSec 2
    if ($Existing.meta.sha256 -eq 'b5ac027e863c5580dab39c8f459e4698d65e9fbec29832c9915448f2087307b7') {
        Start-Process $DemoUrl
        exit 0
    }
} catch {}
$LogDir = Join-Path $ProjectRoot 'data'
Start-Process -FilePath $PythonCommand.Source -ArgumentList @('server.py', '--port', "$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir 'server.log') -RedirectStandardError (Join-Path $LogDir 'server-error.log')
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    Start-Sleep -Milliseconds 300
    try {
        $Ready = Invoke-RestMethod "$DemoUrl/api/overview" -TimeoutSec 2
        if ($Ready.meta.sha256 -eq 'b5ac027e863c5580dab39c8f459e4698d65e9fbec29832c9915448f2087307b7') {
            Start-Process $DemoUrl
            Write-Host "Ready: $DemoUrl"
            exit 0
        }
    } catch {}
}
Write-Host 'Start failed. Check data/server-error.log or choose another port.'
exit 1
