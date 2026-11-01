param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = if ($Python) { $Python } else { Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create a Python virtual environment and install requirements-build.txt first. See README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'tools\ffmpeg.exe'))) {
    throw 'FFmpeg tools are missing. See README.md.'
}
$env:PYTHONPATH = $PSScriptRoot
& $taskPython scripts/make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
& $taskPython scripts/collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
& $taskPython -m PyInstaller --noconfirm Shiying.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
Write-Output 'Built: dist\Shiying\Shiying.exe'
