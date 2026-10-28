from datetime import datetime, timedelta

import pytest
from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla import core
from ayikla.core import ShootSession, ConflictError
from ayikla.metadata import CaptureInfo, burst_groups
from ayikla.compare import BurstCompare


def test_burst_group_undo_after_restart(shoot, make_pair):
    for i in range(5):
        make_pair(shoot, f"IMG_{i}")
    original = {p.name: p.read_bytes() for p in shoot.iterdir()}
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], False)
        session.decide_burst(session.all_photos(), "img_3")
        assert [p.key for p in session.snapshot().kept] == ["img_3"]
        assert len(session.snapshot().rejected) == 4
    with ShootSession(shoot) as session:
        assert session.undo()
        assert [p.key for p in session.snapshot().rejected] == ["img_0"]
        assert len(session.snapshot().pending) == 4
        session.undo()
        assert all((shoot / name).read_bytes() == data for name, data in original.items())


def test_burst_recovers_interrupted_group(shoot, make_pair, monkeypatch):
    for i in range(3):
        make_pair(shoot, f"IMG_{i}")
    original = core.move_no_replace
    calls = []
    def interrupted(source, target):
        if calls:
            raise OSError("simulated interruption")
        calls.append(source)
        original(source, target)
    with ShootSession(shoot) as session:
        monkeypatch.setattr(core, "move_no_replace", interrupted)
        with pytest.raises(OSError):
            session.decide_burst(session.all_photos(), "img_1")
    monkeypatch.setattr(core, "move_no_replace", original)
    with ShootSession(shoot) as session:
        assert session.recovery_count == 1
        assert len(session.snapshot().kept) == 1
        assert len(session.snapshot().rejected) == 2
        session.undo()
        assert len(session.snapshot().pending) == 3


def test_group_collision_changes_nothing(shoot, make_pair):
    for i in range(2):
        make_pair(shoot, f"IMG_{i}")
    (shoot / core.REJECTED).mkdir()
    (shoot / core.REJECTED / "IMG_1.CR3").write_bytes(b"external")
    with ShootSession(shoot) as session:
        with pytest.raises(ConflictError):
            session.decide_burst(session.all_photos(), "img_0")
        assert (shoot / "IMG_0.JPG").exists()
        assert (shoot / "IMG_1.JPG").exists()
        assert not session.stack


def test_burst_groups_use_existing_one_second_rule():
    now = datetime(2026, 10, 29)
    items = {str(i): CaptureInfo(str(i), now + timedelta(seconds=t))
             for i, t in enumerate((0, .5, 1.5, 4, 5))}
    assert burst_groups(items) == [("0", "1", "2"), ("3", "4")]


def test_compare_paging_selection_zoom_pan_and_confirmation(shoot):
    app = QApplication.instance() or QApplication([])
    for i in range(6):
        Image.new("RGB", (1200, 800), "gray").save(shoot / f"{i}.jpg")
    with ShootSession(shoot) as session:
        dialog = BurstCompare(session.all_photos(), "0")
        dialog.show()
        QTest.qWait(30)
        QTest.keyClick(dialog, Qt.Key.Key_Right)
        assert dialog.page == 1
        QTest.keyClick(dialog, Qt.Key.Key_2)
        assert dialog.selected == "5"
        QTest.keyClick(dialog, Qt.Key.Key_F)
        assert all(p.zoomed for p in dialog.panes)
        for pane in dialog.panes:
            pane.image = dialog.panes[0].image
        dialog.pan_all(QPointF(10, 10))
        assert all(p.pan == dialog.panes[0].pan for p in dialog.panes)
        decisions = []
        dialog.committed.connect(lambda photos, key: decisions.append((len(photos), key)))
        QTest.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        assert decisions == [(6, "5")]
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        assert not dialog.isVisible()
