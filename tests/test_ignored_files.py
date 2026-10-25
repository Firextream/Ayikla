"""Card metadata must never enter the photo index or filesystem transactions."""

import ctypes
import json
import stat

import pytest
from PIL import Image

from ayikla.core import EDIT, KEPT, LOG, REJECTED, ConflictError, ShootSession


def set_attributes(path, attributes):
    setter = ctypes.WinDLL("kernel32", use_last_error=True).SetFileAttributesW
    setter.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    setter.restype = ctypes.c_int
    if not setter(str(path), attributes):
        raise ctypes.WinError(ctypes.get_last_error())


@pytest.mark.parametrize("name", ["._IMG_1941.JPG", "._img_1941.cR3", "Thumbs.db",
                                 "THUMBS.DB", "DESKTOP.INI", ".DS_Store", ".ds_store"])
def test_named_metadata_is_ignored_case_insensitively(shoot, make_pair, name):
    make_pair(shoot, "IMG_1941")
    helper = shoot / name
    helper.write_bytes(b"metadata, never an image")
    with ShootSession(shoot) as session:
        photo, = session.snapshot().pending
        assert photo.jpeg.name == "IMG_1941.JPG" and photo.raw.name == "IMG_1941.CR3"
        assert sum(session.ignored_files.values()) == 1
        assert session.ignored_notice
        session.decide(photo, True)
        session.toggle_edit(session.snapshot().kept[0])
        assert sorted(path.name for path in (shoot / EDIT).iterdir()) == ["IMG_1941.CR3", "IMG_1941.JPG"]
        session.undo()
        session.undo()
        assert session.snapshot().pending == (photo,)
        assert helper.read_bytes() == b"metadata, never an image"
        assert name not in (shoot / LOG).read_text("utf-8")


@pytest.mark.parametrize("attributes", [stat.FILE_ATTRIBUTE_HIDDEN, stat.FILE_ATTRIBUTE_SYSTEM,
                                      stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM])
def test_hidden_and_system_photos_are_excluded(shoot, make_pair, attributes):
    make_pair(shoot, "VISIBLE")
    make_pair(shoot, "HIDDEN")
    for extension in ("JPG", "CR3"):
        set_attributes(shoot / f"HIDDEN.{extension}", attributes)
    with ShootSession(shoot) as session:
        assert [photo.key for photo in session.all_photos()] == ["visible"]
        assert session.ignored_files == {"hidden_system": 2}
        session.decide(session.snapshot().pending[0], False)
        assert len(session.snapshot().rejected) == 1
        session.undo()
        assert (shoot / "HIDDEN.JPG").exists() and (shoot / "HIDDEN.CR3").exists()


def test_hidden_raw_is_not_a_pair_or_a_new_raw_conflict(shoot, make_pair):
    make_pair(shoot)
    raw = shoot / "IMG_1234.CR3"
    set_attributes(raw, stat.FILE_ATTRIBUTE_HIDDEN)
    with ShootSession(shoot) as session:
        photo, = session.snapshot().pending
        assert photo.raw is None
        session.decide(photo, True)
        assert raw.read_bytes() == b"dummy raw IMG_1234"
        assert not (shoot / KEPT / raw.name).exists()
        session.toggle_edit(session.snapshot().kept[0])
        assert [path.name for path in (shoot / EDIT).iterdir()] == ["IMG_1234.JPG"]
        session.undo()
        session.undo()
        assert photo.jpeg.exists() and raw.exists()


def test_appledouble_raw_does_not_pair_with_a_real_lone_jpeg(shoot, make_pair):
    make_pair(shoot, raw=False)
    (shoot / "._IMG_1234.CR3").write_bytes(b"metadata")
    with ShootSession(shoot) as session:
        photo, = session.snapshot().pending
        assert photo.raw is None and session.snapshot().total == 1
        session.decide(photo, False)
        assert (shoot / "._IMG_1234.CR3").read_bytes() == b"metadata"
        assert [path.name for path in (shoot / REJECTED).iterdir()] == ["IMG_1234.JPG"]
        assert session.undo() and photo.jpeg.exists()


@pytest.mark.parametrize("folder_name,state", [("", "pending"), (KEPT, "kept"), (REJECTED, "rejected")])
def test_filter_applies_to_all_scanned_folders(shoot, make_pair, folder_name, state):
    folder = shoot / folder_name
    folder.mkdir(exist_ok=True)
    make_pair(folder)
    make_pair(folder, "._IMG_1234")
    (folder / "Thumbs.db").write_bytes(b"metadata")
    (folder / "DIRECTORY.JPG").mkdir()
    with ShootSession(shoot) as session:
        photo, = session.all_photos()
        assert photo.state == state and photo.raw.name == "IMG_1234.CR3"
        assert session.snapshot().total == 1
        assert session.ignored_files == {"appledouble": 2, "metadata": 1}


def test_2180_card_entries_report_1090_helpers(shoot, make_pair):
    for index in range(545):
        make_pair(shoot, f"IMG_{index:04d}")
        make_pair(shoot, f"._IMG_{index:04d}")
    assert len(list(shoot.iterdir())) == 2180
    with ShootSession(shoot) as session:
        assert session.snapshot().total == 545
        assert session.ignored_notice == "1090 macOS helper files (._) ignored"
        assert all(photo.raw is not None for photo in session.all_photos())


def test_mixed_folder_transactions_resume_and_corrupt_jpeg(shoot, make_pair):
    make_pair(shoot, "IMG_1941")
    Image.new("RGB", (24, 16), "gray").save(shoot / "IMG_1941.JPG")
    make_pair(shoot, "CORRUPT")  # Deliberately invalid JPEG bytes, valid filename.
    helpers = {name: b"metadata " + name.encode() for name in
               ("._IMG_1941.JPG", "._IMG_1941.CR3", "._CORRUPT.JPG", "._CORRUPT.CR3",
                "Thumbs.db", "desktop.ini", ".DS_Store")}
    for name, data in helpers.items():
        (shoot / name).write_bytes(data)
    original = {path.name: path.read_bytes() for path in shoot.iterdir()}
    with ShootSession(shoot) as session:
        corrupt, real = session.snapshot().pending
        assert session.snapshot().total == 2 and len(session.all_photos()) == 2
        assert real.raw.name == "IMG_1941.CR3" and corrupt.raw.name == "CORRUPT.CR3"
        session.decide(real, True)
        session.decide(corrupt, False)
        assert (len(session.snapshot().kept), len(session.snapshot().rejected)) == (1, 1)
    with ShootSession(shoot) as session:
        assert session.snapshot().total == 2 and session.ignored_files["appledouble"] == 4
        assert session.undo() and session.undo()
        assert len(session.snapshot().pending) == 2
        assert {name: (shoot / name).read_bytes() for name in original} == original
    for line in (shoot / LOG).read_text("utf-8").splitlines():
        for operation in json.loads(line).get("ops", []):
            assert not operation["src"].split("/")[-1].startswith("._")


@pytest.mark.parametrize("action", ["keep", "edit", "undo"])
def test_newly_hidden_source_is_never_moved_or_copied(shoot, make_pair, action):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        photo, = session.snapshot().pending
        if action != "keep":
            session.decide(photo, True)
            photo, = session.snapshot().kept
        set_attributes(photo.jpeg, stat.FILE_ATTRIBUTE_HIDDEN)
        operation = {"keep": lambda: session.decide(photo, True),
                     "edit": lambda: session.toggle_edit(photo), "undo": session.undo}[action]
        before = (shoot / LOG).read_bytes()
        with pytest.raises(ConflictError, match="Hidden/system"):
            operation()
        assert photo.jpeg.exists() and photo.raw.exists()
        assert (shoot / LOG).read_bytes() == before
        assert session.snapshot().total == 0
