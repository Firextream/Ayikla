# Windows x64, onedir, no console. Whitelist only the Qt runtime/plugins we use.
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('licenses', 'licenses')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'PIL.ImageQt', 'PIL.ImageTk', 'PIL.ImageCms',
              'PIL._imagingcms', 'PIL._webp', 'PIL._avif', 'PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtPdf', 'PySide6.QtNetwork', 'PySide6.QtTest'],
    noarchive=False,
    optimize=0,
)
# Windows 10/11 provides UCRT. Never shadow it with an older DLL accidentally
# found in another tool's PATH. Qt 6 needs the operating system's current UCRT.
def needed_binary(item):
    name = item[0].replace('\\', '/').lower()
    base = name.rsplit('/', 1)[-1]
    if base == 'ucrtbase.dll' or base.startswith('api-ms-win-crt-'):
        return False
    if base == 'opengl32sw.dll':
        return False  # This app uses QWidget/QPainter raster rendering only.
    if '/plugins/' in name:
        return base in {'qwindows.dll', 'qoffscreen.dll', 'qjpeg.dll', 'qico.dll'}
    if base.startswith('qt6') and base.endswith('.dll'):
        return base in {'qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll'}
    return True
a.binaries = [item for item in a.binaries if needed_binary(item)]
a.datas = [item for item in a.datas if '/translations/' not in item[0].replace('\\', '/')]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='Ayikla', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    icon='assets/ayikla.ico', version='assets/version_info.txt',
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Ayikla')
