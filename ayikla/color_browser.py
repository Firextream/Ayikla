"""Modal, cancellable palette browser; results never change shoot decisions."""

from threading import Event

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .colors import TONES, analyze, rank
from .images import ImageCache


class Signals(QObject):
    progress = Signal(int, int)
    finished = Signal(object, object)


class AnalysisTask(QRunnable):
    def __init__(self, photos, cached):
        super().__init__()
        self.photos, self.cached = photos, cached
        self.cancel = Event()
        self.signals = Signals()

    def run(self):
        profiles, failures = {}, {}
        for index, photo in enumerate(self.photos):
            if self.cancel.is_set():
                break
            try:
                signature = ImageCache.key(photo.jpeg, QSize(128, 128))
                profile = self.cached.get(signature)
                if profile is None:
                    profile = analyze(photo.jpeg)
                profiles[photo.key] = (signature, profile)
            except Exception as error:
                failures[photo.key] = str(error)
            if index % 10 == 0 or index + 1 == len(self.photos):
                self.signals.progress.emit(index + 1, len(self.photos))
        self.signals.finished.emit(profiles, failures)


def plain(text):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class ColorBrowser(QDialog):
    activated = Signal(str)
    analyzed = Signal(object)

    def __init__(self, photos, reference, cached, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Color ideas · Ayikla")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(900, 650)
        self.photos = {photo.key: photo for photo in photos}
        self.reference, self.profiles, self.failures = reference, {}, {}
        self.cache_values = cached
        self.closed = False
        self.tiles = {}
        self.results = []
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.images = ImageCache(self, byte_limit=4 * 1024 * 1024)
        self.images.decoded.connect(self._thumbnail)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = plain("Find a palette. Build a post.")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(plain("Explore your kept photos by color. Click a frame to return to it, then E to pick it for editing."))
        controls = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItem("Similar palette to current photo", None)
        for tone in TONES:
            self.filter.addItem(tone, tone)
        if reference is None:
            self.filter.setCurrentIndex(1)
        controls.addWidget(self.filter, 1)
        self.strength = QComboBox()
        for name, value in (("At least 15% of frame", .15), ("At least 30%", .3), ("At least 50%", .5)):
            self.strength.addItem(name, value)
        controls.addWidget(self.strength)
        layout.addLayout(controls)
        name = self.photos[reference].jpeg.name if reference in self.photos else "none"
        self.status = plain("Analyzing kept photos…")
        self.reference_label = plain(f"Reference: {name}")
        layout.addWidget(self.reference_label)
        layout.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.grid = QGridLayout(body)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        layout.addWidget(plain("Top 24 matches · Preview colors, not quality scores. Camera profiles and lighting affect the result. No files are changed."))
        close = QPushButton("Back to photos")
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.filter.setEnabled(False)
        self.strength.setEnabled(False)
        self.filter.currentIndexChanged.connect(self.render)
        self.strength.currentIndexChanged.connect(self.render)
        self.task = AnalysisTask(tuple(photos), dict(cached))
        self.task.signals.progress.connect(self._progress)
        self.task.signals.finished.connect(self._ready)
        self.pool.start(self.task)

    def _progress(self, count, total):
        if not self.closed:
            self.status.setText(f"Analyzing kept JPEGs… {count} / {total}")

    def _ready(self, values, failures):
        if self.closed:
            return
        self.profiles = {key: value[1] for key, value in values.items()}
        self.cache_values.clear()
        self.cache_values.update(dict(values.values()))
        self.failures = failures
        self.filter.setEnabled(True)
        self.analyzed.emit(failures)
        self.render()

    def render(self):
        tone = self.filter.currentData()
        self.strength.setEnabled(tone is not None)
        self.results = rank(self.profiles, tone=tone, reference=self.reference,
                            minimum=self.strength.currentData())
        self.images.clear()
        self.tiles.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            item.widget().deleteLater()
        reference_failed = tone is None and self.reference not in self.profiles
        message = ("Reference unavailable. Choose a color above." if reference_failed else
                   f"{len(self.results)} matches shown · {len(self.profiles)} analyzed")
        if not self.results and not reference_failed:
            message += " · Try a different tone or lower the percentage."
        if self.failures:
            message += f" · {len(self.failures)} unreadable JPEGs skipped (details on hover)"
        self.status.setText(message)
        self.status.setToolTip('\n'.join(f"{self.photos[key].jpeg.name}: {error}" for key, error in self.failures.items()))
        for index, (key, score) in enumerate(self.results):
            photo = self.photos[key]
            card = QWidget()
            column = QVBoxLayout(card)
            thumb = QPushButton()
            thumb.setMinimumSize(160, 106)
            thumb.setIconSize(QSize(156, 100))
            thumb.setToolTip(photo.jpeg.name)
            thumb.clicked.connect(lambda checked=False, selected=key: self.choose(selected))
            self.tiles[str(photo.jpeg)] = thumb
            column.addWidget(thumb)
            name = plain(photo.jpeg.name)
            name.setMaximumWidth(180)
            column.addWidget(name)
            row = QHBoxLayout()
            for color in self.profiles[key].swatches:
                swatch = QLabel()
                swatch.setFixedHeight(12)
                swatch.setStyleSheet(f"background: {color}; border-radius: 2px;")
                swatch.setToolTip(color)
                row.addWidget(swatch)
            column.addLayout(row)
            column.addWidget(plain(f"{score:.0%} {tone.lower()}" if tone else f"{score:.0%} palette overlap"))
            self.grid.addWidget(card, index // 4, index % 4)
        paths = [self.photos[key].jpeg for key, _ in self.results]
        if paths:
            self.images.show(paths[0], paths[1:], QSize(156, 100))

    def _thumbnail(self, path):
        if not self.closed and path in self.tiles:
            from pathlib import Path
            image = self.images.get(Path(path), QSize(156, 100))
            if not image.isNull():
                self.tiles[path].setIcon(QIcon(QPixmap.fromImage(image)))

    def choose(self, key):
        self.accept()
        self.activated.emit(key)

    def done(self, result):
        self.closed = True
        self.task.cancel.set()
        self.pool.waitForDone()
        self.images.close()
        super().done(result)
