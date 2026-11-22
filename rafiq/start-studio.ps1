$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & ./.studio-venv/Scripts/python.exe -m rafiq.studio
}
finally {
    Pop-Location
}
