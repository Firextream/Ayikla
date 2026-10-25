"""Create a shareable ZIP; never include the portable user's settings or shoots."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ayikla import __version__
from ayikla.core import is_link


def package(root: Path, filename: str | None = None) -> Path:
    root = root.resolve(strict=True)
    bundle = root / "dist" / "Ayikla"
    filename = filename or f"Ayikla-{__version__}-Windows-x64.zip"
    if Path(filename).name != filename or not filename.endswith(".zip") or ":" in filename:
        raise ValueError("Release filename must be a ZIP basename")
    destination = root / "dist" / filename

    def checked(path):
        if not path.resolve().is_relative_to(root):
            raise ValueError("Release paths must stay inside the project")
        if any(is_link(part) for part in (path, *path.parents) if part.is_relative_to(root)):
            raise ValueError("Release paths cannot be links")
        return path

    checked(destination)
    runtime = checked(bundle / "_internal")
    if not runtime.is_dir():
        raise FileNotFoundError("Built runtime missing")
    # Only named distribution inputs are allowed at the bundle root. Existing
    # settings, journals, test reports, screenshots and photos are never added.
    inputs = [(bundle / "Ayikla.exe", "Ayikla/Ayikla.exe"),
              (bundle / "MasaustuKisayolu.ps1", "Ayikla/MasaustuKisayolu.ps1"),
              (root / "BETA.md", "Ayikla/BASLANGIC.md")]
    private_names = {"ayikla_settings.jsonl", "ayikla_log.jsonl", ".ayikla.lock"}
    for path in sorted(runtime.rglob("*")):
        checked(path)
        if path.name.casefold() in private_names or path.suffix.casefold() in {".jpg", ".jpeg", ".cr3"}:
            raise ValueError("Unexpected private data in the built runtime")
        if path.is_file():
            inputs.append((path, "Ayikla/" + path.relative_to(bundle).as_posix()))
    for path, _ in inputs:
        checked(path)
        if not path.is_file():
            raise FileNotFoundError(path)
    # Exclusive creation: even a partial previous archive is preserved.
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, name in inputs:
            archive.write(path, name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise OSError("Release ZIP integrity check failed")
    return destination


if __name__ == "__main__":
    result = package(ROOT)
    print(json.dumps({"file": result.relative_to(ROOT).as_posix(), "bytes": result.stat().st_size,
                      "sha256": hashlib.sha256(result.read_bytes()).hexdigest()}, indent=2))
