"""Exercise the built EXE without the project interpreter or sources on its PATH."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
executable = root / "dist" / "Ayikla" / "Ayikla.exe"
output = root / ".tmp" / "frozen-verification" / uuid.uuid4().hex[:12]
output.mkdir(parents=True)
environment = os.environ.copy()
backend = "windows" if "--windows" in sys.argv else "offscreen"
environment["QT_QPA_PLATFORM"] = backend
if backend == "windows":
    environment["AYIKLA_HEADLESS_WINDOWS"] = "1"
environment["TEMP"] = environment["TMP"] = str(root / ".tmp")
environment["PATH"] = str(Path(environment["WINDIR"]) / "System32")
environment["AYIKLA_STATE_DIR"] = str(output / "state")
environment.pop("PYTHONHOME", None)
environment.pop("PYTHONPATH", None)
process = subprocess.run(
    [str(executable), "--smoke-test", str(output)],
    cwd=output, env=environment, capture_output=True, timeout=60,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
results = list(output.glob("smoke-*/result.json"))
if len(results) != 1:
    error_file = output / "startup-error.txt"
    diagnostic = error_file.read_text("utf-8") if error_file.exists() else repr(process.stderr)
    raise SystemExit(f"EXE returned {process.returncode}; no result:\n{diagnostic}")
result = json.loads(results[0].read_text("utf-8"))
result["executable"] = str(executable)
result["bytes"] = executable.stat().st_size
result["package_bytes"] = sum(path.stat().st_size for path in executable.parent.rglob("*") if path.is_file())
result["sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
result["exit_code"] = process.returncode
result["source_on_path"] = False
result["qt_backend"] = backend
result["qt_modules"] = sorted(path.name for path in (executable.parent / "_internal/PySide6").glob("Qt6*.dll"))
result["qt_plugins"] = sorted(path.name for path in (executable.parent / "_internal/PySide6/plugins").rglob("*.dll"))
assert result["qt_modules"] == ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"]
assert result["qt_plugins"] == ["qico.dll", "qjpeg.dll", "qoffscreen.dll", "qwindows.dll"]
assert not list((executable.parent / "_internal").rglob("opengl32sw.dll"))
docs = root / "docs"
docs.mkdir(exist_ok=True)
filename = "verification-windows.json" if backend == "windows" else "verification.json"
(docs / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
for source, target in (("gallery.png", "gallery.png"), ("zoom.png", "zoom.png"), ("info.png", "info.png"),
                       ("filmstrip.png", "filmstrip.png"), ("end.png", "end.png"),
                       ("gallery.png", "arayuz.png"), ("welcome.png", "baslangic.png"),
                       ("folders.png", "folders.png"), ("help.png", "help.png"),
                       ("corrupt.png", "corrupt.png"), ("corrupt-summary.png", "corrupt-summary.png")):
    image = results[0].parent / source
    if image.exists() and backend == "offscreen":
        shutil.copyfile(image, docs / target)
print(json.dumps(result, ensure_ascii=True, indent=2))
sys.exit(0 if result["ok"] and process.returncode == 0 else 1)
