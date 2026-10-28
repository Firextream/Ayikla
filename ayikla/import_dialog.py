"""Cancelable background card import, also available before a shoot is open."""

from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout)

from .importer import import_folder


class ImportSignals(QObject):
    progress = Signal(int, int, str)
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
            result = import_folder(*self.arguments, cancel=self.cancel,
                                   progress=self.signals.progress.emit, active_session=self.session)
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
        self.resize(650, 330)
        layout = QVBoxLayout(self)
        title = QLabel("Copy from your card. Verify every file.")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)
        explanation = QLabel("Source files stay untouched. Matching copies are skipped; different files are never overwritten.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        fields = QFormLayout()
        self.source = QLineEdit()
        self.destination = QLineEdit(destination)
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
        layout.addLayout(fields)
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
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)

    def browse(self, field):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", field.text())
        if folder:
            field.setText(folder)

    def start(self):
        if self.running:
            return
        if not all(field.text().strip() for field in (self.source, self.destination, self.name)):
            self.status.setText("Choose a source, destination root and shoot name.")
            return
        self.running = True
        for control in (self.source, self.destination, self.name, self.start_button, *self.browse_buttons):
            control.setEnabled(False)
        self.status.setText("Scanning source files…")
        self.progress.setRange(0, 0)
        self.task = ImportTask(self.source.text(), self.destination.text(), self.name.text(), self.session)
        self.task.signals.progress.connect(self.update_progress)
        self.task.signals.finished.connect(self.finished_import)
        self.pool.start(self.task)

    def update_progress(self, done, total, filename):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.status.setText(f"{done} / {total} verified or skipped · {filename}")

    def finished_import(self, result, error):
        self.running = False
        self.task = None
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Close")
        if error:
            from .errors import error_message
            self.status.setText(error_message(error))
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            for control in (self.source, self.destination, self.name, self.start_button, *self.browse_buttons):
                control.setEnabled(True)
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
