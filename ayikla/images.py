"""Byte-bounded asynchronous JPEG/TIFF previews, including EXIF orientation."""

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColorSpace, QImage, QImageReader
from PIL import Image, ImageOps

from .file_access import file_guard


def read_image(path: str | Path, bounds: QSize, full_resolution=False) -> tuple[QImage, str]:
    with file_guard(path):
        # The inner frame destroys QImageReader (and closes its QFile) before
        # releasing the guard. Moves can then acquire it without a sharing race.
        return _read_image(path, bounds, full_resolution)


def _read_image(path: str | Path, bounds: QSize, full_resolution=False) -> tuple[QImage, str]:
    if Path(path).suffix.casefold() in {".tif", ".tiff"}:
        return _read_tiff(path, bounds, full_resolution)
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and not full_resolution:
        # The scaled size refers to encoded pixels, before EXIF auto-rotation.
        rotated = bool(reader.transformation().value & 4)
        target = QSize(bounds.height(), bounds.width()) if rotated else bounds
        scaled = size.scaled(target.boundedTo(QSize(3200, 3200)), Qt.AspectRatioMode.KeepAspectRatio)
        if scaled.width() < size.width() or scaled.height() < size.height():
            reader.setScaledSize(scaled)
        # Qt's JPEG handler uses reduced DCT decoding for scaled reads.
        reader.setQuality(49)
    image = reader.read()
    return image, reader.errorString() if image.isNull() else ""


def _read_tiff(path, bounds, full_resolution):
    try:
        with Image.open(path, formats=["TIFF"]) as image:
            profile = image.info.get("icc_profile")
            # Pillow/libtiff handles RGB 16-bit channels; grayscale needs an
            # explicit range conversion (convert('L') alone clips at 255).
            if image.mode.startswith("I;16") or (image.mode == "I" and image.tag_v2.get(258) == (16,)):
                image = image.convert("I").point(lambda value: value / 256).convert("L")
            if not full_resolution:
                target = bounds.boundedTo(QSize(3200, 3200))
                width, height = max(1, target.width()), max(1, target.height())
                # Use Pillow's reduce/thumbnail path before constructing Qt
                # pixels. TIFF codecs may still need to decode the source.
                image.thumbnail((width, height), Image.Resampling.LANCZOS, reducing_gap=3.0)
            image = ImageOps.exif_transpose(image)
            rgb = image.convert("RGB")
            pixels = rgb.tobytes()
            result = QImage(pixels, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()
            if profile:
                result.setColorSpace(QColorSpace.fromIccProfile(profile))
            return result, ""
    except (OSError, ValueError, SyntaxError, OverflowError) as error:
        return QImage(), str(error)


class LoadSignals(QObject):
    finished = Signal(object, QImage, str)


class LoadTask(QRunnable):
    def __init__(self, key: tuple):
        super().__init__()
        self.key = key
        self.signals = LoadSignals()
        self.cancelled = False

    def run(self):
        if self.cancelled:
            self.signals.finished.emit(self.key, QImage(), "cancelled")
            return
        try:
            image, error = read_image(self.key[0], QSize(self.key[3], self.key[4]), self.key[5])
        except Exception as exception:
            image, error = QImage(), str(exception)
        self.signals.finished.emit(self.key, image, error)


class ImageCache(QObject):
    loaded = Signal(str, QImage, str)
    decoded = Signal(str)

    def __init__(self, parent=None, byte_limit=128 * 1024 * 1024):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.cache: OrderedDict[tuple, tuple[QImage, str]] = OrderedDict()
        self.inflight: dict[tuple, LoadTask] = {}
        self.desired: set[tuple] = set()
        self.wanted: tuple | None = None
        self.byte_limit = byte_limit
        self.bytes = 0

    @staticmethod
    def key(path: Path, bounds: QSize, full_resolution=False) -> tuple:
        stat = path.stat()
        return (str(path), stat.st_size, stat.st_mtime_ns,
                max(1, bounds.width()), max(1, bounds.height()), bool(full_resolution))

    def get(self, path: Path, bounds: QSize) -> QImage:
        try:
            key = self.key(path, bounds)
        except OSError:
            return QImage()
        result = self.cache.get(key)
        return result[0] if result else QImage()

    def show(self, current: Path, neighbors: list[Path], bounds: QSize, full_resolution=False) -> None:
        try:
            self.wanted = self.key(current, bounds, full_resolution)
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
        for key, task in self.inflight.items():
            task.cancelled = key not in self.desired
        for key in keys:
            if key in self.cache:
                self.cache.move_to_end(key)
                if key == self.wanted:
                    image, error = self.cache[key]
                    self.loaded.emit(key[0], image, error)
            elif key not in self.inflight:
                task = LoadTask(key)
                task.signals.finished.connect(self._finished)
                self.inflight[key] = task
                self.pool.start(task, 1 if key == self.wanted else 0)

    def _finished(self, key: tuple, image: QImage, error: str) -> None:
        self.inflight.pop(key, None)
        if error == "cancelled":
            if key == self.wanted:
                # A cancelled queued task can become current again before delivery.
                task = LoadTask(key)
                task.signals.finished.connect(self._finished)
                self.inflight[key] = task
                self.pool.start(task, 1)
            return
        if key in self.desired and image.sizeInBytes() <= self.byte_limit:
            previous = self.cache.pop(key, None)
            if previous:
                self.bytes -= previous[0].sizeInBytes()
            self.cache[key] = (image, error)
            self.bytes += image.sizeInBytes()
            while self.bytes > self.byte_limit:
                _, (evicted, _) = self.cache.popitem(last=False)
                self.bytes -= evicted.sizeInBytes()
        if key == self.wanted:
            self.loaded.emit(key[0], image, error)
        self.decoded.emit(key[0])

    def discard_full_resolution(self):
        for key in list(self.cache):
            if key[5]:
                self.bytes -= self.cache.pop(key)[0].sizeInBytes()
        for key, task in self.inflight.items():
            if key[5]:
                task.cancelled = True

    def clear(self) -> None:
        for task in self.inflight.values():
            task.cancelled = True
        self.cache.clear()
        self.bytes = 0
        self.desired.clear()
        self.wanted = None

    def close(self) -> None:
        self.clear()
        self.pool.waitForDone()
