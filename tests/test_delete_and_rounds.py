"""Delete is reversible rejection; round labels explain the actual destinations."""

import json
import time

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.core import EDIT, KEPT, LOG, REJECTED
from ayikla.ui import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait(app, predicate):
    deadline = time.monotonic() + 10
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert predicate(), "UI operation did not finish"
    app.processEvents()


@pytest.fixture
def window(app, monkeypatch):
    def capture_error(window, error):
        window.last_error = error
        window._update_enabled()
    monkeypatch.setattr(MainWindow, "_show_error", capture_error)
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    app.processEvents()


def make_photo(shoot, *, raw=True, corrupt=False):
    jpeg = shoot / "iMg_1941.jPg"
    if corrupt:
        jpeg.write_bytes(b"GENERATED CORRUPT JPEG")
    else:
        Image.new("RGB", (32, 20), "gray").save(jpeg)
    if raw:
        (shoot / "IMG_1941.cR3").write_bytes(b"GENERATED RAW")
    return {path.name: path.read_bytes() for path in shoot.iterdir()}


@pytest.mark.parametrize("raw", [True, False])
@pytest.mark.parametrize("corrupt", [True, False])
def test_delete_moves_pair_and_z_restores_exact_paths(app, window, shoot, raw, corrupt):
    original = make_photo(shoot, raw=raw, corrupt=corrupt)
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and ("Could not open JPEG" in window.canvas.message
                                         if corrupt else not window.canvas.image.isNull()))
    QTest.keyClick(window, Qt.Key.Key_Delete)
    wait(app, lambda: not window.busy and window.current is None)
    assert not hasattr(window, "last_error")
    assert window.session.snapshot().total == 1 and len(window.session.snapshot().rejected) == 1
    assert {path.name: path.read_bytes() for path in (shoot / REJECTED).iterdir()} == original
    assert all(not (shoot / name).exists() for name in original)
    records = [json.loads(line) for line in (shoot / LOG).read_text("utf-8").splitlines()]
    decision = next(record for record in records if record["type"] == "begin")
    assert decision["action"] == "reject" and all(op["kind"] == "move" for op in decision["ops"])
    QTest.keyClick(window, Qt.Key.Key_Z)
    wait(app, lambda: not window.busy and window.current is not None)
    assert {name: (shoot / name).read_bytes() for name in original} == original
    assert not list((shoot / REJECTED).iterdir())


def test_delete_conflict_does_not_overwrite_or_move_jpeg(app, window, shoot):
    original = make_photo(shoot)
    (shoot / REJECTED).mkdir()
    target = shoot / REJECTED / "IMG_1941.CR3"
    target.write_bytes(b"EXISTING FILE")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy)
    before = (shoot / LOG).read_bytes()
    QTest.keyClick(window, Qt.Key.Key_Delete)
    wait(app, lambda: not window.busy and hasattr(window, "last_error"))
    assert target.read_bytes() == b"EXISTING FILE"
    assert {name: (shoot / name).read_bytes() for name in original} == original
    assert (shoot / LOG).read_bytes() == before and not window.session.stack


def test_round_labels_and_actions_distinguish_keep_from_lightroom_copy(app, window, shoot):
    original = make_photo(shoot)
    window.open_folder(shoot)
    wait(app, lambda: not window.busy)
    assert "Keep" in window.keep_button.text() and "Delete" in window.reject_button.text()
    assert "KEEP OR REJECT" in window.round_hint.text() and "01_secilen" in window.round_hint.text()
    assert "_red" in window.round_hint.text() and "saved automatically" in window.round_hint.text()
    QTest.keyClick(window, Qt.Key.Key_H)
    assert all(text in window.canvas.help.text() for text in ("Delete", "no files deleted", "01_secilen", "02_edit"))
    QTest.keyClick(window, Qt.Key.Key_H)
    QTest.keyClick(window, Qt.Key.Key_Return)
    wait(app, lambda: not window.busy)
    assert {name: (shoot / KEPT / name).read_bytes() for name in original} == original
    assert not (shoot / EDIT).exists()
    QTest.keyClick(window, Qt.Key.Key_M)
    assert "LIGHTROOM" in window.round_hint.text() and "02_edit" in window.round_hint.text()
    assert "Pick for editing" in window.mark_button.text()
    QTest.keyClick(window, Qt.Key.Key_E)
    wait(app, lambda: not window.busy)
    assert {name: (shoot / EDIT / name).read_bytes() for name in original} == original
    assert {name: (shoot / KEPT / name).read_bytes() for name in original} == original
    assert "Remove edit pick" in window.mark_button.text()
    before = (shoot / LOG).read_bytes()
    QTest.keyClick(window, Qt.Key.Key_Delete)
    app.processEvents()
    assert not window.busy and (shoot / LOG).read_bytes() == before
    assert window.current.state == "kept" and window.current.key in window.session.edits
    assert not (shoot / REJECTED).exists()
