import os
from pathlib import Path

import pytest

# No real photographs and no system temp folders are used by the suite.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def shoot(tmp_path: Path) -> Path:
    folder = tmp_path / "Çekim 2026"
    folder.mkdir()
    return folder


@pytest.fixture
def make_pair():
    def make(folder: Path, stem="IMG_1234", raw=True):
        (folder / f"{stem}.JPG").write_bytes(b"dummy jpeg " + stem.encode())
        if raw:
            (folder / f"{stem}.CR3").write_bytes(b"dummy raw " + stem.encode())
    return make
