"""Publish a staged build using non-overwriting moves; retain previous contents."""

import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ayikla.core import is_link, move_no_replace


def publish(root: Path, staged: Path) -> Path:
    root, staged = root.resolve(), staged.resolve()
    target = root / "dist" / "Ayikla"
    archived = root / ".tmp" / "replaced-builds" / uuid.uuid4().hex
    for path in (staged, target, archived):
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Build paths must stay inside the project")
        if any(is_link(part) for part in (path, *path.parents) if part.is_relative_to(root)):
            raise ValueError("Build paths cannot be links")
    if staged == target or not (staged / "Ayikla.exe").is_file():
        raise ValueError("Staged executable missing")
    settings = target / "ayikla_settings.jsonl"
    if settings.exists():
        with settings.open("rb") as source, (staged / settings.name).open("xb") as destination:
            shutil.copyfileobj(source, destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = target.exists()
    if previous:
        archived.parent.mkdir(parents=True, exist_ok=True)
        move_no_replace(target, archived)
    try:
        move_no_replace(staged, target)
    except OSError:
        if previous and not target.exists():
            move_no_replace(archived, target)
        raise
    return target


if __name__ == "__main__":
    print(publish(ROOT, Path(sys.argv[1])))
