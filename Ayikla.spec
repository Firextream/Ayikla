# Windows x64, one executable, no console, only the Qt modules this app uses.
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('licenses', 'licenses')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PIL', 'pytest', 'tkinter', 'PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtPdf', 'PySide6.QtNetwork', 'PySide6.QtTest'],
    noarchive=False,
    optimize=0,
)
# Windows 10/11 provides UCRT. Never shadow it with an older DLL accidentally
# found in another tool's PATH. Qt 6 needs the operating system's current UCRT.
a.binaries = [item for item in a.binaries
              if item[0].lower() != 'ucrtbase.dll'
              and not item[0].lower().startswith('api-ms-win-crt-')]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Ayikla', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    icon='assets/ayikla.ico', version='assets/version_info.txt',
)
