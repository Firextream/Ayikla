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
$stagingRoot = Join-Path $PSScriptRoot ('.tmp\package-' + [guid]::NewGuid().ToString('N'))
& $pythonPath -m PyInstaller --noconfirm --distpath $stagingRoot Ayikla.spec
if ($LASTEXITCODE -ne 0) { throw 'Paketleme başarısız.' }
$stagedBundle = Join-Path $stagingRoot 'Ayikla'
Copy-Item -LiteralPath 'scripts\create_shortcut.ps1' -Destination (Join-Path $stagedBundle 'MasaustuKisayolu.ps1')
Copy-Item -LiteralPath 'licenses' -Destination (Join-Path $stagedBundle '_internal') -Recurse -Force
& $pythonPath 'scripts\publish_build.py' $stagedBundle
if ($LASTEXITCODE -ne 0) { throw 'Paket yayinlanamadi. Onceki dosyalar korundu.' }
Get-Item -LiteralPath 'dist\Ayikla\Ayikla.exe' | Select-Object FullName,Length
