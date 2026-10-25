from pathlib import Path

import pytest

from scripts import publish_build


def staged(root):
    path = root / ".tmp" / "staged" / "Ayikla"
    path.mkdir(parents=True)
    (path / "Ayikla.exe").write_bytes(b"new executable")
    return path


def test_rebuild_preserves_old_bundle_and_preferences(tmp_path):
    source = staged(tmp_path)
    old = tmp_path / "dist" / "Ayikla"
    old.mkdir(parents=True)
    (old / "Ayikla.exe").write_bytes(b"old executable")
    (old / "ayikla_settings.jsonl").write_bytes(b"user settings")
    (old / "extra.txt").write_bytes(b"preserve this too")
    result = publish_build.publish(tmp_path, source)
    assert (result / "Ayikla.exe").read_bytes() == b"new executable"
    assert (result / "ayikla_settings.jsonl").read_bytes() == b"user settings"
    archives = list((tmp_path / ".tmp" / "replaced-builds").iterdir())
    assert len(archives) == 1
    assert (archives[0] / "extra.txt").read_bytes() == b"preserve this too"
    assert (archives[0] / "Ayikla.exe").read_bytes() == b"old executable"


def test_publication_rolls_back_without_losing_staged_files(tmp_path, monkeypatch):
    source = staged(tmp_path)
    old = tmp_path / "dist" / "Ayikla"
    old.mkdir(parents=True)
    (old / "Ayikla.exe").write_bytes(b"old")
    real = publish_build.move_no_replace
    def fail_publish(start, end):
        if start == source:
            raise OSError("simulated publish failure")
        real(start, end)
    monkeypatch.setattr(publish_build, "move_no_replace", fail_publish)
    with pytest.raises(OSError):
        publish_build.publish(tmp_path, source)
    assert (old / "Ayikla.exe").read_bytes() == b"old"
    assert (source / "Ayikla.exe").read_bytes() == b"new executable"


def test_publisher_refuses_outside_paths_and_settings_overwrite(tmp_path):
    source = staged(tmp_path)
    with pytest.raises(ValueError):
        publish_build.publish(tmp_path / "other", source)
    old = tmp_path / "dist" / "Ayikla"
    old.mkdir(parents=True)
    (old / "ayikla_settings.jsonl").write_bytes(b"old settings")
    (source / "ayikla_settings.jsonl").write_bytes(b"existing staged settings")
    with pytest.raises(FileExistsError):
        publish_build.publish(tmp_path, source)
    assert (source / "ayikla_settings.jsonl").read_bytes() == b"existing staged settings"
