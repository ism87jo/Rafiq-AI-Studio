$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    py -3.13 -m venv .venv
    $python = Join-Path $PWD '.venv/Scripts/python.exe'
    & $python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    & $python -m pip install -r requirements.txt
    & $python -m pip check
}
finally {
    Pop-Location
}
