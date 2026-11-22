$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    py -3 -m venv .studio-venv
    & ./.studio-venv/Scripts/python.exe -m pip install -r rafiq/studio/requirements.txt
    & ./.studio-venv/Scripts/python.exe -m pip check
}
finally {
    Pop-Location
}
