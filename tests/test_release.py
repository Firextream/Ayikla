import tomllib
import zipfile
from pathlib import Path

import pytest

from ayikla import __version__
from scripts.package_release import package


@pytest.fixture
def bundle(tmp_path):
    directory = tmp_path / "dist" / "Ayikla"
    runtime = directory / "_internal"
    runtime.mkdir(parents=True)
    (directory / "Ayikla.exe").write_bytes(b"generated executable")
    (directory / "MasaustuKisayolu.ps1").write_text("# shortcut", "utf-8")
    (runtime / "Qt6Core.dll").write_bytes(b"generated runtime")
    (runtime / "licenses").mkdir()
    (runtime / "licenses" / "NOTICE.txt").write_bytes(b"license notice")
    (tmp_path / "BETA.md").write_text("Generated beta guide", "utf-8")
    return directory


def test_release_excludes_private_data_and_preserves_all_inputs(tmp_path, bundle):
    for name in ("ayikla_settings.jsonl", "ayikla_log.jsonl", "IMG.JPG", "IMG.CR3", "personal.txt"):
        (bundle / name).write_bytes(b"PRIVATE DATA")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = package(tmp_path)
    with zipfile.ZipFile(result) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "Ayikla/Ayikla.exe", "Ayikla/MasaustuKisayolu.ps1", "Ayikla/GETTING_STARTED.md",
            "Ayikla/_internal/Qt6Core.dll", "Ayikla/_internal/licenses/NOTICE.txt"}
        assert archive.read("Ayikla/Ayikla.exe") == b"generated executable"
        assert all(b"PRIVATE DATA" not in archive.read(name) for name in archive.namelist())
    assert all(p.read_bytes() == data for p, data in before.items())


def test_release_never_overwrites_existing_zip(tmp_path, bundle):
    result = package(tmp_path)
    before = result.read_bytes()
    with pytest.raises(FileExistsError):
        package(tmp_path)
    assert result.read_bytes() == before


@pytest.mark.parametrize("filename", ["../outside.zip", "nested/file.zip", "drive:bad.zip"])
def test_release_rejects_paths(tmp_path, bundle, filename):
    with pytest.raises(ValueError):
        package(tmp_path, filename)
    assert not list((tmp_path / "dist").glob("*.zip"))


@pytest.mark.parametrize("name", ["ayikla_settings.jsonl", "PHOTO.JPG", "PHOTO.RAF", "PHOTO.ARW", "PHOTO.ORF", "SCAN.TIF", "SCAN.TIFF", "PHOTO.xmp"])
def test_release_refuses_unexpected_private_runtime_data(tmp_path, bundle, name):
    (bundle / "_internal" / name).write_bytes(b"private")
    with pytest.raises(ValueError, match="private"):
        package(tmp_path)
    assert not list((tmp_path / "dist").glob("*.zip"))


def test_package_and_windows_version_match():
    root = Path(__file__).resolve().parents[1]
    assert tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]["version"] == __version__
    info = (root / "assets/version_info.txt").read_text("utf-8")
    assert f"StringStruct('FileVersion', '{__version__}')" in info
    assert f"StringStruct('ProductVersion', '{__version__}')" in info
