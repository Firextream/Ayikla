$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Join-Path $PSScriptRoot '.tools\python312\tools\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Önce requirements-dev.txt kur.' }
$env:PYTHONNOUSERSITE = '1'
$env:TEMP = Join-Path $PSScriptRoot '.tmp'
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.tools\pyinstaller-cache'
# Avoid collecting unrelated DLLs from desktop tooling on the inherited PATH.
$env:PATH = @((Split-Path -Parent $pythonPath), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& $pythonPath -c "import runpy; runpy.run_path('scripts/make_icon.py', run_name='__main__')"
if ($LASTEXITCODE -ne 0) { throw 'Simge üretilemedi.' }
& $pythonPath -m PyInstaller --noconfirm Ayikla.spec
if ($LASTEXITCODE -ne 0) { throw 'Paketleme başarısız.' }
Get-Item -LiteralPath 'dist\Ayikla.exe' | Select-Object FullName,Length
