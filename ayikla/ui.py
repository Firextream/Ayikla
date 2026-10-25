"""Turkish keyboard-first desktop interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QRect, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .core import AyiklaError, Photo, ShootSession
from .images import ImageCache
from .metadata import burst_hints, read_metadata
from .preferences import Preferences
from .widgets import FadingOverlay, Filmstrip, PhotoCanvas

STYLE = """
QWidget { background: #1a1a1a; color: #dddddd; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 19px; font-weight: 800; letter-spacing: 5px; color: #dedede; }
QLabel#muted { color: #999999; }
QLabel#hero { font-size: 44px; font-weight: 650; }
QLabel#eyebrow { color: #dedede; font-size: 12px; letter-spacing: 3px; }
QLabel#counter { font-size: 17px; font-weight: 600; }
QLabel#filename { font-size: 17px; font-weight: 600; }
QLabel#badge { border-radius: 6px; padding: 5px 9px; background: #303030; color: #b0b0b0; }
QFrame#bar { background: #202020; border-radius: 12px; }
QPushButton { background: #282828; border: 1px solid #404040; border-radius: 8px;
              padding: 10px 16px; color: #cccccc; font-weight: 600; }
QPushButton:hover { background: #383838; border-color: #777777; }
QPushButton:pressed { background: #444444; }
QPushButton:checked { background: #404040; border-color: #888888; color: #eeeeee; }
QPushButton:disabled { color: #686868; background: #222222; border-color: #303030; }
QPushButton#primary { background: #dedede; color: #1a1a1a; border: 0; padding: 14px 25px; }
QPushButton#primary:hover { background: #eeeeee; }
QPushButton#keep { background: #d2d2d2; color: #1a1a1a; border: 0; min-width: 180px; padding: 14px; }
QPushButton#keep:hover { background: #eeeeee; }
QPushButton#reject { background: #272727; color: #cccccc; border-color: #494949;
                    min-width: 180px; padding: 14px; }
QPushButton#reject:hover { background: #3b3b3b; }
QProgressBar { border: none; background: #303030; max-height: 3px; min-height: 3px; }
QProgressBar::chunk { background: #d2d2d2; }
QToolTip { color: #dddddd; background: #383838; border: 1px solid #777777; padding: 6px; }
QMessageBox { background: #202020; }
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(QColor("#1a1a1a"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#dedede"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        self.preferences = Preferences()
        self.zoomed = False
        self.preview_photo = None
        self.summary_requested = False
        self.metadata = {}
        self.bursts = {}
        self._metadata_task = None
        self._needs_metadata_rescan = False
        self._metadata_pool = QThreadPool(self)
        self._metadata_pool.setMaxThreadCount(1)
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
        self.canvas.activity.connect(self._reveal_overlays)
        self._restore_geometry()

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
        header.addWidget(button("Yardım  ·  H", self.toggle_help))
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
        self.recent_layout = QVBoxLayout()
        intro.addSpacing(12)
        intro.addLayout(self.recent_layout)
        self._update_recent()
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
        self.viewer = QStackedWidget()
        self.viewer.addWidget(self.canvas)
        end_page = QWidget()
        end_layout = QVBoxLayout(end_page)
        end_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.setSpacing(20)
        end_layout.addWidget(label("TUR TAMAMLANDI", "eyebrow"))
        end_layout.addWidget(label("Seçkin hazır.", "hero"))
        self.end_counts = label("", "counter")
        end_layout.addWidget(self.end_counts)
        self.round2_button = button("2. tura geç  ·  M", lambda: self.set_mode("edit"), "primary")
        end_layout.addWidget(self.round2_button)
        self.explorer_button = button("02_edit klasörünü Explorer'da aç", self.open_edit_folder)
        end_layout.addWidget(self.explorer_button)
        end_layout.addWidget(button("Fotoğraflara dön", self.return_to_photos))
        end_layout.addWidget(label("Z ile son kararı geri alabilirsin.", "muted"))
        self.viewer.addWidget(end_page)
        content.addWidget(self.viewer, 1)
        self.filmstrip = Filmstrip()
        self.filmstrip.activated.connect(self.jump_to)
        content.addWidget(self.filmstrip)

        info = QHBoxLayout()
        self.filename = label("", "filename")
        info.addWidget(self.filename)
        self.raw_badge = label("", "badge")
        info.addWidget(self.raw_badge)
        self.edit_badge = label("DÜZENLEMEYE AYRILDI", "badge")
        self.edit_badge.setStyleSheet("color: #dedede; background: #363636;")
        info.addWidget(self.edit_badge)
        info.addStretch()
        self.remaining = label("", "muted")
        info.addWidget(self.remaining)
        self.zoom_button = button("%100  ·  F", self.toggle_zoom)
        self.info_button = button("Bilgi  ·  I", self.toggle_info)
        self.strip_button = button("Şerit  ·  T", self.toggle_filmstrip)
        for control in (self.zoom_button, self.info_button, self.strip_button):
            info.addWidget(control)
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
        self.summary_button = button("Tur özeti", self.show_summary)
        actions.addWidget(self.summary_button)
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
        footer.addWidget(label("F  %100  ·  I  Bilgi  ·  T  Şerit", "muted"))
        layout.addLayout(footer)
        self.undo_button.setEnabled(False)
        self.setCentralWidget(root)
        self.toast = FadingOverlay(root)

    def _update_recent(self):
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.preferences.recent:
            self.recent_layout.addWidget(label("SON KLASÖRLER", "muted"))
        for path in self.preferences.recent:
            control = button(Path(path).name, lambda checked=False, value=path: self.open_folder(value))
            control.setToolTip(path)
            self.recent_layout.addWidget(control)

    def _restore_geometry(self):
        values = self.preferences.window
        if values:
            rectangle = QRect(*values["geometry"])
            screen = self.screen().availableGeometry()
            if not screen.intersects(rectangle):
                rectangle.moveTopLeft(screen.topLeft())
            self.setGeometry(rectangle)

    def show_saved_state(self):
        values = self.preferences.window
        if values.get("fullscreen", True):
            self.showFullScreen()
        elif values.get("maximized"):
            self.showMaximized()
        else:
            self.show()

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
        self.preview_photo = None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.clear()
        self.folder_label.setText(self.session.root.name)
        self.folder_label.setToolTip(str(self.session.root))
        self.setWindowTitle(f"{self.session.root.name} — Ayikla")
        self.mode = self.session.view["mode"]
        self.pages.setCurrentIndex(1)
        recovered = self.session.recovery_count
        self.feedback.setText("Yarım kalan işlem güvenle tamamlandı." if recovered else self._success)
        try:
            self.preferences.add_recent(self.session.root)
            self._update_recent()
        except OSError:
            self.feedback.setText("Son klasör kaydedilemedi. Uygulama klasörüne yazma izni ver.")
        self._load_metadata()
        self.refresh(self.session.view["key"], rescan=False, allow_preview=True)

    def _operation_finished(self, _result, error):
        self.busy = False
        self._task = None
        if error:
            self._show_error(error)
            return
        self.feedback.setText(self._success)
        self.notify(self._success)
        self.preview_photo = None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.discard_full_resolution()
        if self.session:
            self.mode = self.session.view["mode"]
            if self._needs_metadata_rescan:
                self._load_metadata()
                self._needs_metadata_rescan = False
            self.refresh(self.session.view["key"], rescan=False)

    def _show_error(self, error):
        from .errors import error_message
        message = error_message(error)
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
        if self.summary_requested:
            return None
        return self.preview_photo or (self.photos[self.index] if self.photos and self.index < len(self.photos) else None)

    def refresh(self, preferred: str | None = None, *, rescan=True, allow_preview=False):
        if not self.session:
            return
        try:
            snapshot = self.session.rescan() if rescan else self.session.snapshot()
            self.photos = snapshot.pending if self.mode == "cull" else snapshot.kept
            self.index = next((i for i, photo in enumerate(self.photos) if photo.key == preferred), 0)
            if allow_preview and preferred and not any(photo.key == preferred for photo in self.photos):
                self.preview_photo = next((photo for photo in self.session.all_photos() if photo.key == preferred), None)
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
                self.raw_badge.setStyleSheet("" if photo.raw else "color: #cccccc; background: #303030;")
                self.raw_badge.show()
                self.edit_badge.setVisible(photo.key in self.session.edits)
                self.mark_button.setText("Seçimi kaldır  ·  E" if photo.key in self.session.edits else "Düzenlemeye ayır  ·  E")
                self.canvas.message = "Yükleniyor…"
                self.session.save_view(self.mode, photo.key)
                self._request_image()
                self.viewer.setCurrentIndex(0)
                if self.preview_photo:
                    self.counter.setText(f"{photo.jpeg.name}  ·  {'elenen kare · önizleme' if photo.state == 'rejected' else 'önizleme'}")
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
                self.viewer.setCurrentIndex(1 if snapshot.total and (self.mode == "cull" or self.summary_requested) else 0)
            self.end_counts.setText(f"{snapshot.total} kare  ·  {len(snapshot.kept)} seçilen  ·  "
                                    f"{len(snapshot.rejected)} elenen\n{len(self.session.edits)} düzenlemeye ayrılan")
            self.round2_button.setEnabled(bool(snapshot.kept))
            self.filmstrip.set_items(self.session.all_photos(), photo.key if photo else None, self.session.edits)
            self._update_overlays()
            self.canvas.update()
            self._update_enabled()
        except (OSError, AyiklaError) as error:
            self._show_error(error)

    def _request_image(self):
        if self.current is None:
            return
        neighbors = [self.photos[index].jpeg for offset in (1, 2, -1)
                     if 0 <= (index := self.index + offset) < len(self.photos)]
        bounds = (self.canvas.size() - QSize(16, 16)) * self.devicePixelRatioF()
        if getattr(self, "zoomed", False):
            self.cache.show(self.current.jpeg, [], bounds, full_resolution=True)
        else:
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
            control.setEnabled(has_photo and self.preview_photo is None)
        for control in (self.zoom_button, self.info_button):
            control.setEnabled(has_photo)
        self.strip_button.setEnabled(enabled)
        self.previous_button.setEnabled(has_photo and self.index > 0)
        self.next_button.setEnabled(has_photo and self.index + 1 < len(self.photos))
        self.undo_button.setEnabled(enabled and bool(self.session.stack))
        self.open_button.setEnabled(not self.busy and not bool(self.session and self.session.pending_id))
        self.retry_button.setVisible(self.session is not None)
        self.retry_button.setEnabled(not self.busy and not bool(self.session and self.session.faulted))
        self.keep_button.setVisible(self.mode == "cull")
        self.reject_button.setVisible(self.mode == "cull")
        self.mark_button.setVisible(self.mode == "edit")
        self.summary_button.setVisible(self.mode == "edit")
        self.summary_button.setEnabled(enabled)

    def navigate(self, offset: int):
        if self.busy or not self.session or self.session.pending_id or self.session.faulted or not self.photos:
            return
        target = min(max(0, self.index + offset), len(self.photos) - 1)
        if self.preview_photo:
            catalog = self.session.all_photos()
            position = next(i for i, photo in enumerate(catalog) if photo.key == self.preview_photo.key)
            allowed = {photo.key: i for i, photo in enumerate(self.photos)}
            step = 1 if offset > 0 else -1
            target = next((allowed[catalog[i].key] for i in range(position + step,
                           len(catalog) if step > 0 else -1, step) if catalog[i].key in allowed), None)
            if target is None:
                return
        if self.mode == "edit" and offset > 0 and self.index == len(self.photos) - 1:
            self.show_summary()
            return
        self.preview_photo = None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.discard_full_resolution()
        self.refresh(self.photos[target].key, rescan=False)

    def set_mode(self, mode: str):
        if self.busy or not self.session or self.session.pending_id or self.session.faulted:
            return
        self.mode = mode
        self.preview_photo = None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.discard_full_resolution()
        self.refresh(rescan=False)

    def decide(self, keep: bool):
        if not self.current or self.mode != "cull" or not self.session or self.preview_photo:
            return
        photo = self.current
        remaining = list(self.photos)
        remaining.pop(self.index)
        next_key = remaining[min(self.index, len(remaining) - 1)].key if remaining else None
        self._run(lambda: self.session.decide(photo, keep, next_key), "Dosyalar taşınıyor…",
                  "Seçildi" if keep else "Elendi")

    def toggle_edit(self):
        if not self.current or self.mode != "edit" or not self.session or self.preview_photo:
            return
        photo = self.current
        marked = photo.key in self.session.edits
        self._run(lambda: self.session.toggle_edit(photo), "Düzenleme seçimi kaydediliyor…",
                  "Edit seçimi kaldırıldı; kopyalar saklandı" if marked else "Edit'e eklendi")

    def undo(self):
        if self.session and self.session.stack:
            self._run(self.session.undo, "Son karar geri alınıyor…", "Geri alındı")

    def retry(self):
        if self.session:
            self._needs_metadata_rescan = True
            self._run(self.session.recover_pending, "Klasör ve yarım kalan işlem kontrol ediliyor…", "Klasör yenilendi")

    def notify(self, message):
        self.toast.reveal(message)
        self.toast.move(max(12, (self.centralWidget().width() - self.toast.width()) // 2),
                        max(12, self.centralWidget().height() - self.toast.height() - 72))

    def toggle_zoom(self):
        if not self.current or self.busy:
            return
        self.zoomed = not self.zoomed
        self.canvas.set_zoom(self.zoomed)
        self.canvas.image = QImage()
        self.cache.discard_full_resolution()
        self._request_image()
        self._update_overlays()

    def toggle_info(self):
        if not self.current:
            return
        if self.canvas.info.isVisible() and self.canvas.info.effect.opacity() > .5:
            self.canvas.info.dismiss()
        else:
            self._show_info()

    def _show_info(self):
        if self.current:
            info = self.metadata.get(self.current.key)
            self.canvas.info.reveal(info.text() if info else f"{self.current.jpeg.name}\nEXIF bilgisi okunuyor…")
            self.canvas.position_overlays()

    def toggle_help(self):
        if self.canvas.help.isVisible():
            self.canvas.help.dismiss()
        else:
            self.canvas.help.reveal("KLAVYE\n\n→ / Enter   Seç     ← / X   Ele\nBoşluk / ↓   Sonraki     ↑   Önceki\n"
                                    "Z   Geri al     M   Turu değiştir     E   Edit seçimi\n"
                                    "F   %100 / Sığdır     Sürükle   Kaydır\nI   Çekim bilgisi     T   Film şeridi\n"
                                    "H / ?   Yardım     Esc   Yardımı / yakınlaştırmayı kapat\nF11   Tam ekran     Ctrl+O   Klasör aç",
                                    auto_fade=False)
            self.canvas.position_overlays()
        if not self.session:
            self.pages.setCurrentIndex(1 if not self.canvas.help.isHidden() else 0)
            self.canvas.message = "Başlamak için bir çekim klasörü seç."

    def toggle_filmstrip(self):
        self.filmstrip.setVisible(not self.filmstrip.isVisible())
        self.filmstrip.request_visible()

    def _reveal_overlays(self):
        self._update_overlays()
        if self.canvas.info.isVisible():
            self._show_info()

    def _update_overlays(self):
        photo = self.current
        if not photo:
            self.canvas.hud.dismiss()
            self.canvas.info.dismiss()
            return
        hint = self.bursts.get(photo.key)
        parts = ([f"Seri {hint[0]}/{hint[1]}"] if hint else []) + (["%100 · sürükleyerek kaydır · F sığdır"] if self.zoomed else [])
        if parts:
            self.canvas.hud.reveal("  ·  ".join(parts))
        else:
            self.canvas.hud.dismiss()
        if self.canvas.info.isVisible():
            self._show_info()
        self.canvas.position_overlays()

    def _load_metadata(self):
        root, photos = self.session.root, self.session.all_photos()
        self.metadata, self.bursts = {}, {}
        task = OperationTask(lambda: (root, {photo.key: read_metadata(photo.jpeg) for photo in photos}))
        task.signals.finished.connect(self._metadata_loaded)
        self._metadata_task = task
        self._metadata_pool.start(task)

    def _metadata_loaded(self, result, error):
        if not error and self.session and result[0] == self.session.root:
            self.metadata = result[1]
            self.bursts = burst_hints(self.metadata)
            self._update_overlays()

    def jump_to(self, key):
        if self.busy or not self.session or self.session.pending_id:
            return
        photo = next((photo for photo in self.session.all_photos() if photo.key == key), None)
        if not photo:
            return
        self.mode = "edit" if photo.state == "kept" else "cull"
        self.preview_photo = photo if photo.state == "rejected" else None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.discard_full_resolution()
        self.refresh(key, rescan=False, allow_preview=True)

    def show_summary(self):
        if self.session and not self.busy:
            self.summary_requested = True
            self.preview_photo = None
            self.refresh(rescan=False)

    def return_to_photos(self):
        self.summary_requested = False
        self.refresh(rescan=False)

    def open_edit_folder(self):
        if not self.session or self.busy:
            return
        try:
            path = self.session._path("02_edit")
            path.mkdir(exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise OSError("Explorer açılamadı. Çekim klasöründeki 02_edit klasörünü elle aç.")
        except (OSError, AyiklaError) as error:
            self._show_error(error)

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
            if self.canvas.help.isVisible():
                self.canvas.help.dismiss()
            elif self.zoomed:
                self.toggle_zoom()
            elif self.isFullScreen():
                self.showMaximized()
        elif key in (Qt.Key.Key_H, Qt.Key.Key_Question):
            self.toggle_help()
        elif key == Qt.Key.Key_O and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.choose_folder()
        elif self.busy or event.isAutoRepeat() or not self.session or self.session.pending_id or self.session.faulted:
            return
        elif key == Qt.Key.Key_M:
            self.set_mode("edit" if self.mode == "cull" else "cull")
        elif key == Qt.Key.Key_Z:
            self.undo()
        elif key == Qt.Key.Key_F:
            self.toggle_zoom()
        elif key == Qt.Key.Key_I:
            self.toggle_info()
        elif key == Qt.Key.Key_T:
            self.toggle_filmstrip()
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
        self.filmstrip.cache.close()
        self._metadata_pool.waitForDone()
        rectangle = self.normalGeometry() if self.isFullScreen() or self.isMaximized() else self.geometry()
        try:
            self.preferences.save_window([rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()],
                                         self.isFullScreen(), self.isMaximized())
        except OSError:
            self.feedback.setText("Pencere ayarı kaydedilemedi. Uygulama klasörüne yazma izni ver.")
        if self.session:
            self.session.close()
        event.accept()
