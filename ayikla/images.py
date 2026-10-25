"""Bounded asynchronous JPEG decoding, including EXIF orientation."""

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader


def read_image(path: str | Path, bounds: QSize) -> tuple[QImage, str]:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    # Decode no larger than the display envelope. A square envelope also handles
    # portrait photos whose stored pixels are landscape with an EXIF rotation.
    envelope = QSize(max(bounds.width(), bounds.height()), max(bounds.width(), bounds.height()))
    if size.isValid():
        from PySide6.QtCore import Qt
        scaled = size.scaled(envelope, Qt.AspectRatioMode.KeepAspectRatio)
        if scaled.width() < size.width() or scaled.height() < size.height():
            reader.setScaledSize(scaled)
    image = reader.read()
    return image, reader.errorString() if image.isNull() else ""


class LoadSignals(QObject):
    finished = Signal(object, QImage, str)


class LoadTask(QRunnable):
    def __init__(self, key: tuple, bounds: QSize):
        super().__init__()
        self.key, self.bounds = key, bounds
        self.signals = LoadSignals()

    def run(self):
        try:
            image, error = read_image(self.key[0], self.bounds)
        except Exception as exception:
            image, error = QImage(), str(exception)
        self.signals.finished.emit(self.key, image, error)


class ImageCache(QObject):
    loaded = Signal(str, QImage, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.cache: OrderedDict[tuple, tuple[QImage, str]] = OrderedDict()
        self.inflight: dict[tuple, LoadTask] = {}
        self.desired: set[tuple] = set()
        self.wanted: tuple | None = None
        self.limit = 5
        self.byte_limit = 160 * 1024 * 1024

    @staticmethod
    def key(path: Path, bounds: QSize) -> tuple:
        stat = path.stat()
        # Round size up to limit repeated decoding during small window resizes.
        edge = min(4096, ((max(bounds.width(), bounds.height(), 640) + 255) // 256) * 256)
        return str(path), stat.st_size, stat.st_mtime_ns, edge

    def show(self, current: Path, neighbors: list[Path], bounds: QSize) -> None:
        try:
            self.wanted = self.key(current, bounds)
        except OSError as error:
            self.wanted = None
            self.loaded.emit(str(current), QImage(), str(error))
            return
        keys = [self.wanted]
        for path in neighbors:
            try:
                keys.append(self.key(path, bounds))
            except OSError:
                continue
        self.desired = set(keys)
        for key in keys:
            if key in self.cache:
                self.cache.move_to_end(key)
                if key == self.wanted:
                    image, error = self.cache[key]
                    self.loaded.emit(key[0], image, error)
            elif key not in self.inflight:
                task = LoadTask(key, QSize(key[3], key[3]))
                task.signals.finished.connect(self._finished)
                self.inflight[key] = task
                self.pool.start(task, 1 if key == self.wanted else 0)

    def _finished(self, key: tuple, image: QImage, error: str) -> None:
        self.inflight.pop(key, None)
        if key in self.desired:
            self.cache[key] = (image, error)
            self.cache.move_to_end(key)
        while (len(self.cache) > self.limit
               or sum(item[0].sizeInBytes() for item in self.cache.values()) > self.byte_limit):
            self.cache.popitem(last=False)
        if key == self.wanted:
            self.loaded.emit(key[0], image, error)

    def clear(self) -> None:
        self.cache.clear()
        self.desired.clear()
        self.wanted = None

    def close(self) -> None:
        self.pool.clear()
        self.pool.waitForDone()

