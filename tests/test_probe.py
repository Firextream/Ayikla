import json

from PySide6.QtCore import QEvent, QObject

from ayikla.probe import StartupProbe, install_probe


def test_startup_probe_is_opt_in(monkeypatch):
    monkeypatch.delenv("AYIKLA_STARTUP_PROBE", raising=False)
    window = QObject()
    install_probe(window)
    assert not hasattr(window, "_startup_probe")


def test_startup_probe_writes_only_first_paint(tmp_path, monkeypatch):
    path = tmp_path / "ready.json"
    monkeypatch.setenv("AYIKLA_STARTUP_PROBE", str(path))
    scheduled = []
    monkeypatch.setattr("ayikla.probe.QTimer.singleShot", lambda delay, callback: scheduled.append(callback))
    class Window(QObject):
        def close(self):
            pass
    window = Window()
    probe = StartupProbe(window)
    assert not probe.eventFilter(window, QEvent(QEvent.Type.Show))
    assert not path.exists()
    probe.eventFilter(window, QEvent(QEvent.Type.Paint))
    first = json.loads(path.read_text("utf-8"))
    probe.eventFilter(window, QEvent(QEvent.Type.Paint))
    assert json.loads(path.read_text("utf-8")) == first
    assert len(scheduled) == 1
