$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Join-Path $PSScriptRoot '.tools\python312\tools\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Python 3.12 ortamı yok. README içindeki geliştirme kurulumunu uygula.'
}
$env:PYTHONNOUSERSITE = '1'
& $pythonPath -m ayikla @args
exit $LASTEXITCODE
