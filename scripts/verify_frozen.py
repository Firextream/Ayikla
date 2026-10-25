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
executable = root / "dist" / "Ayikla.exe"
output = root / ".tmp" / "frozen-verification" / uuid.uuid4().hex[:12]
output.mkdir(parents=True)
environment = os.environ.copy()
environment["QT_QPA_PLATFORM"] = "offscreen"
environment["TEMP"] = environment["TMP"] = str(root / ".tmp")
environment["PATH"] = str(Path(environment["WINDIR"]) / "System32")
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
result["sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
result["exit_code"] = process.returncode
result["source_on_path"] = False
docs = root / "docs"
docs.mkdir(exist_ok=True)
(docs / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
for source, target in (("gallery.png", "arayuz.png"), ("welcome.png", "baslangic.png")):
    image = results[0].parent / source
    if image.exists():
        shutil.copyfile(image, docs / target)
print(json.dumps(result, ensure_ascii=True, indent=2))
sys.exit(0 if result["ok"] and process.returncode == 0 else 1)
