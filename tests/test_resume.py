import shutil
import time
from datetime import datetime

from PIL import Image
from PySide6.QtWidgets import QApplication

from ayikla.core import ShootSession, KEPT, LOG
from ayikla.ui import MainWindow


def photo(folder, name, second):
    exif = Image.Exif()
    exif[34665] = {36867: f"2026:10:29 12:00:{second:02d}"}
    Image.new("RGB", (60, 40), "gray").save(folder / f"{name}.jpg", exif=exif)


def test_bookmark_travels_with_shoot_and_restores_round_two(shoot, tmp_path):
    photo(shoot, "one", 10)
    photo(shoot, "two", 20)
    with ShootSession(shoot) as session:
        for item in session.snapshot().pending:
            session.decide(item, True)
        session.save_view("edit", "two")
        session.save_view("edit", None)  # Round summary retains the last photo.
    destination = tmp_path / "portable shoot"
    shutil.copytree(shoot, destination)
    with ShootSession(destination) as session:
        assert session.resume_position == ("edit", "two", True)
        assert session.resume["filename"] == "two.jpg"
        assert session.resume["capture_time"] == "2026-10-29T12:00:20"


def test_moved_file_falls_back_to_nearest_undecided_capture(shoot):
    for name, second in (("first", 1), ("bookmark", 20), ("near", 22), ("last", 40)):
        photo(shoot, name, second)
    with ShootSession(shoot) as session:
        session.save_view("cull", "bookmark")
    (shoot / KEPT).mkdir()
    (shoot / "bookmark.jpg").rename(shoot / KEPT / "bookmark.jpg")
    with ShootSession(shoot) as session:
        assert session.resume_position == ("cull", "near", True)


def test_renamed_file_uses_capture_time_not_filename_sort(shoot):
    photo(shoot, "bookmarked", 20)
    photo(shoot, "aaa", 50)
    with ShootSession(shoot) as session:
        session.save_view("cull", "bookmarked")
    (shoot / "bookmarked.jpg").rename(shoot / "zzz.jpg")
    with ShootSession(shoot) as session:
        assert session.resume_position == ("cull", "zzz", True)


def test_missing_capture_time_falls_back_deterministically(shoot, make_pair):
    make_pair(shoot, "one")
    make_pair(shoot, "two")
    with ShootSession(shoot) as session:
        session.save_view("cull", "two")
    (shoot / "two.JPG").rename(shoot / "three.JPG")
    with ShootSession(shoot) as session:
        assert session.resume_position == ("cull", "one", True)


def test_resume_toast_and_start_from_first_do_not_change_decisions(shoot, monkeypatch):
    photo(shoot, "one", 10)
    photo(shoot, "two", 20)
    with ShootSession(shoot) as session:
        session.save_view("cull", "two")
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    errors = []
    monkeypatch.setattr(window, "_show_error", errors.append)
    window.show()
    def wait():
        deadline = time.monotonic() + 10
        while window.busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        app.processEvents()
        assert not window.busy and not errors
    try:
        window.open_folder(shoot)
        wait()
        assert window.current.key == "two" and window.mode == "cull"
        assert window.toast.text() == "Resumed at two · round 1"
        assert window.start_first_button.isVisible()
        before = list(window.session.stack)
        window.start_first_button.click()
        assert window.current.key == "one"
        assert window.session.stack == before
        assert len(window.session.snapshot().pending) == 2
    finally:
        wait()
        window.close()
