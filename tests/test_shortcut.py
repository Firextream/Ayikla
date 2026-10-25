import os
import subprocess
from pathlib import Path


def test_shortcut_script_creates_correct_target_and_never_overwrites(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "create_shortcut.ps1"
    executable = tmp_path / "Ayikla.exe"
    executable.write_bytes(b"generated dummy executable")
    command = [str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
               "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-DestinationDirectory", str(tmp_path), "-ExecutablePath", str(executable)]
    first = subprocess.run(command, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert first.returncode == 0, first.stderr.decode(errors="replace")
    shortcut = tmp_path / "Ayikla.lnk"
    before = shortcut.read_bytes()
    assert before and str(executable).encode("utf-16-le") in before
    second = subprocess.run(command, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert second.returncode != 0
    assert shortcut.read_bytes() == before
