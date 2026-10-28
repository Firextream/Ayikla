"""English presentation and compatibility with the previous Turkish release."""

import json
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ayikla.core import KEPT, LOG, RecoveryError, ShootSession, fingerprint
from ayikla.errors import error_message
from ayikla.metadata import CaptureInfo
from ayikla.ui import MainWindow


def test_english_start_help_and_errors():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.open_button.text() == "Open"
        assert window.retry_button.text() == "Retry"
        assert "Keep" in window.keep_button.text()
        assert "Reject" in window.reject_button.text()
        window.toggle_help()
        assert "KEYBOARD" in window.canvas.help.text()
        assert "no files deleted" in window.canvas.help.text()
        assert "copy to 02_edit" in window.canvas.help.text()
        assert "Check write permission" in error_message(PermissionError())
    finally:
        window.close()
        app.processEvents()


def test_english_exif_labels_preserve_unicode_filename():
    text = CaptureInfo("İstanbul_çığ.JPG").text()
    assert text.startswith("İstanbul_çığ.JPG")
    assert all(label in text for label in ("Taken", "Shutter", "Aperture", "ISO", "Focal length", "Lens"))


def test_journal_errors_keep_recovery_advice_with_english_capitalization():
    for message in ("Journal line cannot be read (2).", "Invalid journal structure (2)."):
        assert "Preserve the journal unchanged" in error_message(RecoveryError(message))


def test_english_release_reopens_and_undoes_turkish_release_journal(shoot):
    # Captured from v1.1.1b1 (f5728d5) using generated files. Fingerprints
    # depend on the filesystem, so substitute only the generated files' IDs.
    folder = shoot / KEPT
    folder.mkdir()
    expected = {"IMG_0001.JPG": b"generated legacy jpeg", "IMG_0001.CR3": b"generated legacy raw"}
    for name, content in expected.items():
        (folder / name).write_bytes(content)
    fixture = Path(__file__).parent / "fixtures/v1.1.1b1-keep.jsonl"
    records = [json.loads(line) for line in fixture.read_text("utf-8").splitlines()]
    for record in records:
        for operation in record.get("ops", []):
            operation["fingerprint"] = fingerprint(shoot / operation["dst"])
    (shoot / LOG).write_text("".join(json.dumps(record) + "\n" for record in records), "utf-8")
    with ShootSession(shoot) as session:
        assert len(session.snapshot().kept) == 1
        assert session.undo()
        assert session.snapshot().total == 1 and len(session.snapshot().pending) == 1
        assert all((shoot / name).read_bytes() == data for name, data in expected.items())
