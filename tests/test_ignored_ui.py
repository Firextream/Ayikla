"""Real corrupt JPEGs remain actionable; metadata never reaches the viewer."""

import time

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.core import KEPT, REJECTED
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
    monkeypatch.setattr(MainWindow, "_show_error", capture_error)
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    app.processEvents()


@pytest.mark.parametrize("keep", [True, False])
def test_corrupt_error_card_decision_summary_and_undo(app, window, shoot, make_pair, keep):
    make_pair(shoot, "CORRUPT")
    make_pair(shoot, "._CORRUPT")
    (shoot / "Thumbs.db").write_bytes(b"metadata")
    original = (shoot / "CORRUPT.JPG").read_bytes()
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and "Could not open JPEG" in window.canvas.message)
    assert not hasattr(window, "last_error")
    assert window.current.key == "corrupt" and window.current.raw is not None
    assert window.session.snapshot().total == 1 and len(window.filmstrip.items) == 1
    assert "2 macOS helper files (._) ignored" in window.ignored_action.text()
    assert window.ignored_action.isVisible() and not window.ignored_action.isEnabled()
    assert window.keep_button.isEnabled() and window.reject_button.isEnabled()
    QTest.keyClick(window, Qt.Key.Key_Return if keep else Qt.Key.Key_X)
    wait(app, lambda: not window.busy and window.viewer.currentIndex() == 1)
    destination = KEPT if keep else REJECTED
    assert (shoot / destination / "CORRUPT.JPG").read_bytes() == original
    assert (shoot / destination / "CORRUPT.CR3").exists()
    assert f"{destination}/CORRUPT.JPG" in window.end_errors.toPlainText()
    assert not window.end_errors.isHidden()
    assert "._" not in window.end_errors.toPlainText()
    QTest.keyClick(window, Qt.Key.Key_Z)
    wait(app, lambda: not window.busy and window.current is not None)
    assert (shoot / "CORRUPT.JPG").read_bytes() == original
    assert window.current.key == "corrupt" and window.session.snapshot().total == 1
    for extension in ("JPG", "CR3"):
        assert (shoot / f"._CORRUPT.{extension}").exists()
    assert (shoot / "Thumbs.db").read_bytes() == b"metadata"
    assert "CORRUPT.JPG" in window.end_errors.toPlainText()


def test_clean_folder_has_no_ignore_notice_or_error_list(app, window, shoot):
    Image.new("RGB", (24, 16), "gray").save(shoot / "GOOD.JPG")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and not window.canvas.image.isNull())
    assert not window.ignored_action.isVisible() and not window.ignored_action.text()
    assert window.end_errors.isHidden() and not window.end_errors.toPlainText()
    window.decode_failures.add("good")
    window._image_loaded(str(window.current.jpeg), window.canvas.image, "")
    assert not window.decode_failures and not window.end_errors.toPlainText()
