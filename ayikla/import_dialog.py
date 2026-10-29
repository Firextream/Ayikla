"""Cancelable background card import, also available before a shoot is open."""

import time
from pathlib import PureWindowsPath
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QProgressBar, QPushButton, QStyle, QStyleOptionFrame, QVBoxLayout)

from . import importer
from .importer import import_folder


def short_path(path):
    """E:\\…\\DCIM\\100CANON: the drive and the last two folders."""
    parts = PureWindowsPath(path).parts
    if len(parts) <= 4:
        return str(path)
    return str(PureWindowsPath(parts[0], "…", *parts[-2:]))


class PathField(QLineEdit):
    """Edits the full path; while not focused shows E:\\…\\DCIM\\100CANON (full path in the tooltip)."""

    def __init__(self, text=""):
        super().__init__(text)
        self.textChanged.connect(self.setToolTip)
        self.setToolTip(text)

    def shown_text(self):
        width = self.contentsRect().width() - 12
        return self.fontMetrics().elidedText(short_path(self.text()), Qt.TextElideMode.ElideMiddle, width)

    def paintEvent(self, event):
        if self.hasFocus() or not self.text():
            return super().paintEvent(event)
        painter = QPainter(self)
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_PanelLineEdit, option, painter, self)
        painter.setPen(self.palette().color(self.foregroundRole()) if self.isEnabled()
                       else self.palette().color(self.palette().ColorGroup.Disabled, self.palette().ColorRole.Text))
        painter.drawText(self.contentsRect().adjusted(6, 0, -6, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.shown_text())


def size_text(value):
    return f"{value / 1e9:.1f} GB" if value >= 1e9 else f"{value / 1e6:.0f} MB"


class ImportSignals(QObject):
    progress = Signal(int, int, str)
    bytes = Signal(object, object)
    finished = Signal(object, object)


class ImportTask(QRunnable):
    def __init__(self, source, destination, name, session):
        super().__init__()
        self.arguments = source, destination, name
        self.session = session
        self.cancel = Event()
        self.signals = ImportSignals()

    def run(self):
        try:
            result = import_folder(*self.arguments, cancel=self.cancel, progress=self.signals.progress.emit,
                                   on_bytes=self.signals.bytes.emit, active_session=self.session)
            self.signals.finished.emit(result, None)
        except Exception as error:
            self.signals.finished.emit(None, error)


class ImportDialog(QDialog):
    completed = Signal(object)

    def __init__(self, destination="", session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.task = None
        self.running = False
        self.setWindowTitle("Import from card")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(720)
        self.resize(760, 380)
        self.bytes = (0, 0)
        self.started = None
        layout = QVBoxLayout(self)
        title = QLabel("Copy from your card. Verify every file.")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)
        explanation = QLabel("Source files stay untouched. Matching copies are skipped; different files are never overwritten.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.cards = QHBoxLayout()  # removable drives with a DCIM folder, offered first
        self.cards.setSpacing(8)
        layout.addLayout(self.cards)
        fields = QFormLayout()
        self.source = PathField()
        self.destination = PathField(destination)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Shoot name · e.g. photo-club")
        self.browse_buttons = []
        for caption, field in (("Card / source folder", self.source), ("Destination root", self.destination)):
            row = QHBoxLayout()
            row.addWidget(field)
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda checked=False, target=field: self.browse(target))
            row.addWidget(browse)
            self.browse_buttons.append(browse)
            fields.addRow(caption, row)
        fields.addRow("Shoot name", self.name)
        self.folder_preview = QLabel()
        self.folder_preview.setObjectName("muted")
        self.folder_preview.setTextFormat(Qt.TextFormat.PlainText)
        fields.addRow("", self.folder_preview)
        self.name.textChanged.connect(self.update_preview)
        self.update_preview()
        layout.addLayout(fields)
        self.find_cards()
        self.status = QLabel("Creates YYYY-MM-DD_<name> in the destination root. Nested card folders are scanned.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        actions.addStretch()
        self.start_button = QPushButton("Import and open")
        self.start_button.clicked.connect(self.start)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.set_copying(False)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)

    def find_cards(self):
        try:
            found = importer.card_folders()
        except OSError:
            found = []
        if not found:
            return
        self.cards.addWidget(QLabel("Card found:"))
        for folder in found:
            choose = QPushButton(f"{folder.drive}\\  ·  DCIM")
            choose.setToolTip(str(folder))
            choose.clicked.connect(lambda checked=False, value=folder: self.source.setText(str(value)))
            self.cards.addWidget(choose)
        self.cards.addStretch(1)
        if not self.source.text():
            self.source.setText(str(found[0]))

    def update_preview(self):
        name = self.name.text()
        if not name.strip():
            self.folder_preview.setText("Creates YYYY-MM-DD_<name>")
        elif importer.valid_shoot_name(name):
            self.folder_preview.setText(f"Creates  {importer.shoot_folder_name(name)}")
        else:
            self.folder_preview.setText('A shoot name cannot contain \\ / : * ? " < > |')

    def browse(self, field):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", field.text())
        if folder:
            field.setText(folder)

    def set_copying(self, copying):
        self.running = copying
        for control in (self.source, self.destination, self.name, self.start_button, *self.browse_buttons):
            control.setEnabled(not copying)
        for control, primary in ((self.start_button, not copying), (self.cancel_button, copying)):
            control.setObjectName("primary" if primary else "")
            control.setAutoDefault(False)
            control.setDefault(primary)
            control.style().unpolish(control)
            control.style().polish(control)
            control.update()
        if copying:
            self.cancel_button.setFocus()

    def start(self):
        if self.running:
            return
        if not all(field.text().strip() for field in (self.source, self.destination, self.name)):
            self.status.setText("Choose a source, destination root and shoot name.")
            return
        self.set_copying(True)
        self.status.setText("Scanning source files…")
        self.progress.setRange(0, 0)
        self.task = ImportTask(self.source.text(), self.destination.text(), self.name.text(), self.session)
        self.started = time.monotonic()
        self.task.signals.progress.connect(self.update_progress)
        self.task.signals.bytes.connect(self.update_bytes)
        self.task.signals.finished.connect(self.finished_import)
        self.pool.start(self.task)

    def update_bytes(self, done, total):
        self.bytes = (done, total)

    def update_progress(self, done, total, filename):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        copied, size = self.bytes
        parts = [f"Importing… {done} / {total} files"]
        if size:
            parts.append(size_text(size))
            elapsed = time.monotonic() - self.started if self.started else 0
            if copied and elapsed >= 2 and copied < size:
                parts.append(f"~{max(1, round(elapsed * (size - copied) / copied))} s")
        self.status.setText(" · ".join(parts))
        self.status.setToolTip(filename)

    def finished_import(self, result, error):
        self.set_copying(False)
        self.task = None
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Close")
        if error:
            from .errors import error_message
            self.status.setText(error_message(error))
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            return
        self.completed.emit(result)
        self.accept()

    def reject(self):
        if self.running:
            self.task.cancel.set()
            self.cancel_button.setText("Cancelling…")
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling · keeping verified files and discarding partial staging data…")
            return
        super().reject()

    def closeEvent(self, event):
        if self.running:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
