import time

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.preferences import Preferences
from ayikla.ui import MainWindow


def wait(app, predicate):
    deadline = time.monotonic() + 10
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    app.processEvents()
    assert predicate()


def test_ctrl_i_imports_opens_and_remembers_destination(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source, destination = tmp_path / "card", tmp_path / "shoots"
    source.mkdir()
    destination.mkdir()
    Image.new("RGB", (80, 60), "red").save(source / "IMG_1.JPG")
    (source / "IMG_1.CR3").write_bytes(b"generated RAW")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    window = MainWindow()
    errors = []
    monkeypatch.setattr(window, "_show_error", errors.append)
    window.show()
    try:
        QTest.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
        dialog = window.import_dialog
        assert dialog and dialog.isVisible()
        dialog.source.setText(str(source))
        dialog.destination.setText(str(destination))
        dialog.name.setText("club")
        dialog.start_button.click()
        assert not dialog.start_button.isEnabled() and not dialog.start_button.isDefault()
        assert dialog.cancel_button.isEnabled() and dialog.cancel_button.isDefault()
        assert dialog.cancel_button.objectName() == "primary"
        wait(app, lambda: window.session is not None and not window.busy and not dialog.running)
        assert dialog.start_button.isEnabled() and dialog.start_button.isDefault()
        assert dialog.cancel_button.objectName() != "primary"
        assert not errors
        assert window.session.root.parent == destination
        assert window.current.key == "img_1"
        assert len(window.session.stack) == 1
        assert Preferences().import_destination == str(destination)
        assert {p.name: p.read_bytes() for p in source.iterdir()} == before
        window.choose_import()
        assert window.import_dialog.destination.text() == str(destination)
        window.import_dialog.reject()
        window.undo()
        wait(app, lambda: not window.busy)
        assert not window.session.snapshot().pending
    finally:
        wait(app, lambda: not window.busy)
        window.close()


def test_cancel_dialog_is_cooperative_and_keeps_source(tmp_path):
    app = QApplication.instance() or QApplication([])
    source, destination = tmp_path / "card", tmp_path / "shoots"
    source.mkdir()
    destination.mkdir()
    (source / "test.CR3").write_bytes(b"generated RAW" * 1000)
    window = MainWindow()
    window.show()
    try:
        window.choose_import()
        dialog = window.import_dialog
        dialog.source.setText(str(source))
        dialog.destination.setText(str(destination))
        dialog.name.setText("cancelled")
        dialog.start()
        dialog.reject()
        wait(app, lambda: not dialog.running)
        assert not dialog.isVisible()
        assert (source / "test.CR3").read_bytes() == b"generated RAW" * 1000
        assert not list(destination.rglob("*.part"))
        wait(app, lambda: not window.busy)
    finally:
        window.close()
