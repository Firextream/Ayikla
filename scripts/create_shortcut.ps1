param(
    [string]$DestinationDirectory = [Environment]::GetFolderPath('Desktop'),
    [string]$ExecutablePath = ''
)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows required.' }
if (-not $ExecutablePath) {
    $ExecutablePath = Join-Path $PSScriptRoot 'Ayikla.exe'
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        $ExecutablePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\Ayikla\Ayikla.exe'
    }
}
$resolvedExe = (Resolve-Path -LiteralPath $ExecutablePath).Path
$resolvedDestination = (Resolve-Path -LiteralPath $DestinationDirectory).Path
$shortcutPath = Join-Path $resolvedDestination 'Ayikla.lnk'
if (Test-Path -LiteralPath $shortcutPath) { throw "Shortcut already exists; nothing overwritten: $shortcutPath" }
$temporaryPath = Join-Path $PSScriptRoot ('.shortcut-' + [guid]::NewGuid().ToString('N') + '.lnk')
$shellObject = New-Object -ComObject WScript.Shell
$shortcutObject = $shellObject.CreateShortcut($temporaryPath)
$shortcutObject.TargetPath = $resolvedExe
$shortcutObject.WorkingDirectory = Split-Path -Parent $resolvedExe
$shortcutObject.IconLocation = $resolvedExe + ',0'
$shortcutObject.Description = 'Ayikla 1.1'
$shortcutObject.Save()
# The two-argument .NET move fails atomically if a shortcut appeared meanwhile.
[IO.File]::Move($temporaryPath, $shortcutPath)
Write-Output $shortcutPath
