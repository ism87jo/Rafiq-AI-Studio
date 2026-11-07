$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & ./.venv/Scripts/python.exe main.py --cpu --offline --listen 127.0.0.1 --disable-auto-launch --disable-all-custom-nodes
}
finally {
    Pop-Location
}
