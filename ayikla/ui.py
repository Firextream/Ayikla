"""Turkish keyboard-first desktop interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .core import AyiklaError, Photo, ShootSession
from .images import ImageCache

STYLE = """
QWidget { background: #101211; color: #e7ece8; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 19px; font-weight: 800; letter-spacing: 5px; color: #c4f19b; }
QLabel#muted { color: #8c9990; }
QLabel#hero { font-size: 44px; font-weight: 650; }
QLabel#eyebrow { color: #c4f19b; font-size: 12px; letter-spacing: 3px; }
QLabel#counter { font-size: 17px; font-weight: 600; }
QLabel#filename { font-size: 17px; font-weight: 600; }
QLabel#badge { border-radius: 6px; padding: 5px 9px; background: #252e27; color: #a8bcad; }
QFrame#bar { background: #181d19; border-radius: 12px; }
QPushButton { background: #202721; border: 1px solid #313b32; border-radius: 8px;
              padding: 10px 16px; color: #cad4cc; font-weight: 600; }
QPushButton:hover { background: #303b30; border-color: #687c62; }
QPushButton:pressed { background: #3a4938; }
QPushButton:checked { background: #34472b; border-color: #829f65; color: #d4f6b8; }
QPushButton:disabled { color: #657066; background: #1a201b; border-color: #272f28; }
QPushButton#primary { background: #c4f19b; color: #182111; border: 0; padding: 14px 25px; }
QPushButton#primary:hover { background: #d5ffb1; }
QPushButton#keep { background: #b7e98d; color: #182510; border: 0; min-width: 180px; padding: 14px; }
QPushButton#keep:hover { background: #d0ffad; }
QPushButton#reject { background: #352523; color: #efb5a9; border-color: #61413a;
                    min-width: 180px; padding: 14px; }
QPushButton#reject:hover { background: #50332e; }
QProgressBar { border: none; background: #222b23; max-height: 3px; min-height: 3px; }
QProgressBar::chunk { background: #b7e98d; }
QToolTip { color: #e7ece8; background: #303b30; border: 1px solid #687c62; padding: 6px; }
QMessageBox { background: #181d19; }
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(QColor("#172015"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#c4f19b"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawRoundedRect(27, 23, 74, 82, 12, 12)
    painter.drawLine(43, 66, 59, 82)
    painter.drawLine(59, 82, 87, 48)
    painter.end()
    return QIcon(pixmap)


def label(text: str, name: str = "") -> QLabel:
    result = QLabel(text)
    result.setObjectName(name)
    return result


def button(text: str, callback, name: str = "") -> QPushButton:
    result = QPushButton(text)
    result.setObjectName(name)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    result.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    result.clicked.connect(callback)
    return result


class PhotoCanvas(QWidget):
    resized = Signal()

    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.message = ""
        self.setMinimumSize(240, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b0e0c"))
        if not self.image.isNull():
            area = self.rect().adjusted(12, 12, -12, -12)
            size = self.image.size().scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = area.x() + (area.width() - size.width()) // 2
            y = area.y() + (area.height() - size.height()) // 2
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(x, y, self.image.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            painter.setPen(QColor("#9cab9d"))
            painter.setFont(QFont("Segoe UI", 18))
            painter.drawText(self.rect().adjusted(30, 30, -30, -30),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class OperationSignals(QObject):
    finished = Signal(object, object)


class OperationTask(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = OperationSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.operation(), None)
        except Exception as error:
            self.signals.finished.emit(None, error)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session: ShootSession | None = None
        self.photos: tuple[Photo, ...] = ()
        self.index = 0
        self.mode = "cull"
        self.busy = False
        self._task = None
        self._success = ""
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.cache = ImageCache(self)
        self.cache.loaded.connect(self._image_loaded)
        self.setWindowTitle("Ayikla")
        self.setWindowIcon(app_icon())
        self.resize(1380, 900)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(180)
        self._resize_timer.timeout.connect(self._request_image)
        self.canvas.resized.connect(lambda: self._resize_timer.start())

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(label("AYIKLA", "brand"))
        header.addSpacing(18)
        self.folder_label = label("Çekimden seçkiye.", "muted")
        self.folder_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self.folder_label, 1)
        self.open_button = button("Klasör aç  ·  Ctrl+O", self.choose_folder)
        header.addWidget(self.open_button)
        self.full_button = button("Tam ekran  ·  F11", self.toggle_fullscreen)
        header.addWidget(self.full_button)
        layout.addLayout(header)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        welcome = QWidget()
        intro = QVBoxLayout(welcome)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setSpacing(22)
        intro.addWidget(label("BİR ÇEKİM. İKİ TUR.", "eyebrow"))
        intro.addWidget(label("İyi kareleri ayır.\nDüzenlemeye hazırla.", "hero"))
        description = label("1  Ayıkla: JPG + CR3 birlikte taşınır.\n"
                            "2  Düzenleme seç: seçtiklerin Lightroom için kopyalanır.", "muted")
        description.setStyleSheet("font-size: 17px; line-height: 1.5;")
        intro.addWidget(description)
        intro.addSpacing(8)
        start = button("Çekim klasörü seç", self.choose_folder, "primary")
        intro.addWidget(start, 0, Qt.AlignmentFlag.AlignLeft)
        intro.addWidget(label("Silme yok. Üzerine yazma yok. Z ile geri al.", "muted"))
        self.pages.addWidget(welcome)

        gallery = QWidget()
        content = QVBoxLayout(gallery)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        toolbar = QHBoxLayout()
        self.cull_button = button("1  Ayıkla", lambda: self.set_mode("cull"))
        self.edit_button = button("2  Düzenleme seç  ·  M", lambda: self.set_mode("edit"))
        for control in (self.cull_button, self.edit_button):
            control.setCheckable(True)
            toolbar.addWidget(control)
        toolbar.addStretch()
        self.counter = label("", "counter")
        toolbar.addWidget(self.counter)
        content.addLayout(toolbar)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        content.addWidget(self.progress)
        self.canvas = PhotoCanvas()
        content.addWidget(self.canvas, 1)

        info = QHBoxLayout()
        self.filename = label("", "filename")
        info.addWidget(self.filename)
        self.raw_badge = label("", "badge")
        info.addWidget(self.raw_badge)
        self.edit_badge = label("DÜZENLEMEYE AYRILDI", "badge")
        self.edit_badge.setStyleSheet("color: #c4f19b; background: #2d4024;")
        info.addWidget(self.edit_badge)
        info.addStretch()
        self.remaining = label("", "muted")
        info.addWidget(self.remaining)
        content.addLayout(info)

        controls = QFrame()
        controls.setObjectName("bar")
        actions = QHBoxLayout(controls)
        actions.setContentsMargins(14, 12, 14, 12)
        self.reject_button = button("Ele  ·  ← / X", lambda: self.decide(False), "reject")
        actions.addWidget(self.reject_button)
        actions.addStretch()
        self.previous_button = button("↑  Önceki", lambda: self.navigate(-1))
        self.next_button = button("Sonraki  ↓ / Boşluk", lambda: self.navigate(1))
        actions.addWidget(self.previous_button)
        actions.addWidget(self.next_button)
        actions.addStretch()
        self.keep_button = button("Seç  ·  → / Enter", lambda: self.decide(True), "keep")
        actions.addWidget(self.keep_button)
        self.mark_button = button("Düzenlemeye ayır  ·  E", self.toggle_edit, "keep")
        actions.addWidget(self.mark_button)
        content.addWidget(controls)
        self.pages.addWidget(gallery)

        footer = QHBoxLayout()
        self.undo_button = button("Geri al  ·  Z", self.undo)
        footer.addWidget(self.undo_button)
        self.feedback = label("Bir çekim klasörü seçerek başla.", "muted")
        self.feedback.setWordWrap(True)
        footer.addWidget(self.feedback, 1)
        self.retry_button = button("Yeniden dene", self.retry)
        self.retry_button.hide()
        footer.addWidget(self.retry_button)
        footer.addWidget(label("Esc  Pencere  ·  F11  Tam ekran", "muted"))
        layout.addLayout(footer)
        self.undo_button.setEnabled(False)
        self.setCentralWidget(root)

    def choose_folder(self):
        if self.busy:
            return
        path = QFileDialog.getExistingDirectory(self, "Çekim klasörünü seç",
                                               str(self.session.root) if self.session else "")
        if path:
            self.open_folder(path)

    def open_folder(self, path: str | Path):
        if self.busy:
            return
        if self.session and Path(path).resolve() == self.session.root:
            self.refresh()
            return
        self._run(lambda: ShootSession(path), "Çekim ve günlük açılıyor…", "Çekim hazır.", opening=True)

    def _run(self, operation, message: str, success: str, opening=False):
        if self.busy:
            return
        self.busy = True
        self._success = success
        self.feedback.setText(message)
        self._update_enabled()
        self._task = OperationTask(operation)
        self._task.signals.finished.connect(self._folder_opened if opening else self._operation_finished)
        self._pool.start(self._task)

    def _folder_opened(self, result, error):
        self.busy = False
        self._task = None
        if error:
            self._show_error(error)
            return
        if self.session:
            self.session.close()
        self.session = result
        self.cache.clear()
        self.folder_label.setText(self.session.root.name)
        self.folder_label.setToolTip(str(self.session.root))
        self.setWindowTitle(f"{self.session.root.name} — Ayikla")
        self.mode = self.session.view["mode"]
        self.pages.setCurrentIndex(1)
        recovered = self.session.recovery_count
        self.feedback.setText("Yarım kalan işlem güvenle tamamlandı." if recovered else self._success)
        self.refresh(self.session.view["key"])

    def _operation_finished(self, _result, error):
        self.busy = False
        self._task = None
        if error:
            self._show_error(error)
            return
        self.feedback.setText(self._success)
        if self.session:
            self.mode = self.session.view["mode"]
            self.refresh(self.session.view["key"])

    def _show_error(self, error):
        message = str(error)
        if self.session and self.session.faulted:
            message += "\nGünlük yazımı doğrulanamadı. Disk sorununu giderip uygulamayı yeniden aç."
        elif self.session and self.session.pending_id:
            message += "\nİşlem yarım kaldı. Hedef çakışmasını veya disk sorununu giderip Yeniden dene'ye bas."
        self.feedback.setText(message)
        self._update_enabled()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("İşlem tamamlanamadı")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.button(QMessageBox.StandardButton.Ok).setText("Tamam")
        box.exec()

    @property
    def current(self) -> Photo | None:
        return self.photos[self.index] if self.photos and self.index < len(self.photos) else None

    def refresh(self, preferred: str | None = None):
        if not self.session:
            return
        try:
            snapshot = self.session.snapshot()
            self.photos = snapshot.pending if self.mode == "cull" else snapshot.kept
            self.index = next((i for i, photo in enumerate(self.photos) if photo.key == preferred), 0)
            if self.mode == "cull":
                position = len(snapshot.kept) + len(snapshot.rejected) + self.index + 1 if self.photos else snapshot.total
                self.counter.setText(f"{position} / {snapshot.total}  ·  {len(snapshot.kept)} seçilen  ·  {len(snapshot.rejected)} elenen")
                self.remaining.setText(f"{len(snapshot.pending)} kararsız kare")
            else:
                position = self.index + 1 if self.photos else 0
                self.counter.setText(f"{position} / {len(snapshot.kept)}  ·  {len(self.session.edits)} düzenlemeye ayrılan")
                self.remaining.setText("01_secilen → 02_edit · kopya")
            self.progress.setRange(0, max(snapshot.total, 1))
            self.progress.setValue(len(snapshot.kept) + len(snapshot.rejected))
            self.cull_button.setChecked(self.mode == "cull")
            self.edit_button.setChecked(self.mode == "edit")
            photo = self.current
            self.canvas.image = QImage()
            if photo:
                self.filename.setText(photo.jpeg.name)
                self.raw_badge.setText("JPG + CR3" if photo.raw else "⚠ CR3 eşleşmesi yok")
                self.raw_badge.setStyleSheet("" if photo.raw else "color: #e9c486; background: #3c3222;")
                self.raw_badge.show()
                self.edit_badge.setVisible(photo.key in self.session.edits)
                self.mark_button.setText("Seçimi kaldır  ·  E" if photo.key in self.session.edits else "Düzenlemeye ayır  ·  E")
                self.canvas.message = "Yükleniyor…"
                self.session.save_view(self.mode, photo.key)
                self._request_image()
            else:
                self.cache.clear()
                self.filename.setText("1. tur tamamlandı" if self.mode == "cull" and snapshot.total else "Fotoğraf yok")
                self.raw_badge.hide()
                self.edit_badge.hide()
                if self.mode == "cull":
                    self.canvas.message = ("Ayıklama tamamlandı.\nM ile düzenlemeye ayıracağın kareleri seç."
                                           if snapshot.total else "Bu klasörde JPG/JPEG fotoğraf bulunamadı.")
                else:
                    self.canvas.message = "Henüz seçilen fotoğraf yok.\n1. turda sağ ok veya Enter ile fotoğraf seç."
                self.session.save_view(self.mode, None)
            self.canvas.update()
            self._update_enabled()
        except (OSError, AyiklaError) as error:
            self._show_error(error)

    def _request_image(self):
        if self.current is None:
            return
        neighbors = [self.photos[index].jpeg for offset in (1, -1, 2, -2)
                     if 0 <= (index := self.index + offset) < len(self.photos)]
        bounds = self.canvas.size() * self.devicePixelRatioF()
        self.cache.show(self.current.jpeg, neighbors, bounds)

    def _image_loaded(self, path: str, image: QImage, error: str):
        if self.current and path == str(self.current.jpeg):
            self.canvas.image = image
            self.canvas.message = f"JPEG açılamadı.\n{self.current.jpeg.name}\n{error}" if error else ""
            self.canvas.update()

    def _update_enabled(self):
        blocked = self.busy or bool(self.session and (self.session.pending_id or self.session.faulted))
        enabled = self.session is not None and not blocked
        has_photo = enabled and self.current is not None
        for control in (self.cull_button, self.edit_button):
            control.setEnabled(enabled)
        for control in (self.keep_button, self.reject_button, self.mark_button):
            control.setEnabled(has_photo)
        self.previous_button.setEnabled(has_photo and self.index > 0)
        self.next_button.setEnabled(has_photo and self.index + 1 < len(self.photos))
        self.undo_button.setEnabled(enabled and bool(self.session.stack))
        self.open_button.setEnabled(not self.busy and not bool(self.session and self.session.pending_id))
        self.retry_button.setVisible(bool(self.session and self.session.pending_id))
        self.retry_button.setEnabled(not self.busy and not bool(self.session and self.session.faulted))
        self.keep_button.setVisible(self.mode == "cull")
        self.reject_button.setVisible(self.mode == "cull")
        self.mark_button.setVisible(self.mode == "edit")

    def navigate(self, offset: int):
        if self.busy or not self.session or self.session.pending_id or self.session.faulted or not self.photos:
            return
        target = min(max(0, self.index + offset), len(self.photos) - 1)
        self.refresh(self.photos[target].key)

    def set_mode(self, mode: str):
        if self.busy or not self.session or self.session.pending_id or self.session.faulted:
            return
        self.mode = mode
        self.refresh()

    def decide(self, keep: bool):
        if not self.current or self.mode != "cull" or not self.session:
            return
        photo = self.current
        remaining = list(self.photos)
        remaining.pop(self.index)
        next_key = remaining[min(self.index, len(remaining) - 1)].key if remaining else None
        self._run(lambda: self.session.decide(photo, keep, next_key), "Dosyalar taşınıyor…",
                  f"{photo.jpeg.name} → {'01_secilen' if keep else '_red'}  ·  Z ile geri al")

    def toggle_edit(self):
        if not self.current or self.mode != "edit" or not self.session:
            return
        photo = self.current
        marked = photo.key in self.session.edits
        self._run(lambda: self.session.toggle_edit(photo), "Düzenleme seçimi kaydediliyor…",
                  "Seçim kaldırıldı; kopyalar silinmeden saklandı." if marked else "JPG + varsa CR3, 02_edit içine kopyalandı.")

    def undo(self):
        if self.session and self.session.stack:
            self._run(self.session.undo, "Son karar geri alınıyor…", "Son karar geri alındı.")

    def retry(self):
        if self.session:
            self._run(self.session.recover_pending, "Yarım kalan işlem tamamlanıyor…", "İşlem tamamlandı.")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showMaximized()
        elif key == Qt.Key.Key_O and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.choose_folder()
        elif self.busy or event.isAutoRepeat() or not self.session or self.session.pending_id or self.session.faulted:
            return
        elif key == Qt.Key.Key_M:
            self.set_mode("edit" if self.mode == "cull" else "cull")
        elif key == Qt.Key.Key_Z:
            self.undo()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.navigate(-1 if key == Qt.Key.Key_Up else 1)
        elif self.mode == "cull" and key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.decide(True)
        elif self.mode == "cull" and key in (Qt.Key.Key_Left, Qt.Key.Key_X):
            self.decide(False)
        elif self.mode == "edit" and key == Qt.Key.Key_E:
            self.toggle_edit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.busy:
            self.feedback.setText("Dosya işlemi sürüyor; tamamlanınca pencereyi kapatabilirsin.")
            event.ignore()
            return
        self.cache.close()
        if self.session:
            self.session.close()
        event.accept()
