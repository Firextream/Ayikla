"""English keyboard-first desktop interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRunnable, QRect, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLayout, QMainWindow, QMessageBox,
    QMenu, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from . import __version__
from .core import EDIT, KEPT, REJECTED, AyiklaError, Photo, ShootSession
from .images import ImageCache
from .metadata import burst_hints, read_metadata
from .preferences import Preferences
from .widgets import ElidedLabel, FadingOverlay, Filmstrip, PhotoCanvas

STYLE = """
QWidget { background: #1a1a1a; color: #dddddd; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 17px; font-weight: 700; letter-spacing: 4px; color: #eeeeee; }
QLabel#muted { color: #999999; }
QLabel#hero { font-size: 40px; font-weight: 600; color: #eeeeee; }
QLabel#eyebrow { color: #999999; font-size: 11px; letter-spacing: 2px; }
QLabel#counter { font-size: 14px; font-weight: 600; color: #dddddd; }
QLabel#filename { font-size: 13px; font-weight: 600; color: #dddddd; }
QLabel#badge { border-radius: 4px; padding: 4px 7px; background: #292929; color: #aaaaaa; font-size: 11px; }
QLabel#stepNumber { font-size: 24px; font-weight: 500; color: #777777; }
QLabel#stepTitle { font-size: 14px; font-weight: 600; color: #e0e0e0; }
QLabel#summaryTitle { font-size: 32px; font-weight: 600; color: #eeeeee; }
QLabel#summaryCounts { font-size: 17px; color: #cccccc; }
QFrame#stepCard, QFrame#summaryCard { background: #202020; border: 1px solid #333333; border-radius: 12px; }
QFrame#bar { background: #202020; border: 1px solid #303030; border-radius: 10px; }
QPushButton { background: #262626; border: 1px solid #3a3a3a; border-radius: 6px;
              padding: 7px 12px; color: #cccccc; font-weight: 500; }
QPushButton:hover { background: #323232; border-color: #666666; color: #eeeeee; }
QPushButton:pressed { background: #3c3c3c; }
QPushButton:checked { background: #383838; border-color: #777777; color: #eeeeee; }
QPushButton#ghost { background: transparent; border-color: transparent; color: #999999; }
QPushButton#ghost:hover { background: #282828; border-color: #3a3a3a; color: #dddddd; }
QPushButton#recent { text-align: left; background: #202020; border-color: #303030; padding: 9px 12px; }
QPushButton#recent:hover { background: #292929; border-color: #555555; }
QPushButton:disabled { color: #686868; background: #222222; border-color: #303030; }
QPushButton#ghost:disabled { color: #555555; background: transparent; border-color: transparent; }
QPushButton#primary { background: #dedede; color: #1a1a1a; border: 0; padding: 12px 24px; font-weight: 600; }
QPushButton#primary:hover { background: #eeeeee; }
QPushButton#keep { background: #d2d2d2; color: #1a1a1a; border: 0; min-width: 154px; padding: 10px 18px; font-weight: 600; }
QPushButton#keep:hover { background: #eeeeee; }
QPushButton#reject { background: #252525; color: #cccccc; border-color: #454545;
                    min-width: 154px; padding: 10px 18px; }
QPushButton#reject:hover { background: #3b3b3b; }
QPushButton#keep:disabled, QPushButton#reject:disabled, QPushButton#primary:disabled {
    background: #292929; color: #606060; border: 1px solid #333333; }
QScrollBar:horizontal { background: #252525; height: 8px; margin: 0; }
QScrollBar::handle:horizontal { background: #555555; min-width: 28px; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QScrollBar:vertical { background: #202020; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #555555; min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QProgressBar { border: none; background: #2a2a2a; max-height: 2px; min-height: 2px; }
QProgressBar::chunk { background: #888888; }
QPlainTextEdit { background: #1c1c1c; border: 1px solid #393939; border-radius: 6px; padding: 8px; color: #cccccc; }
QMenu { background: #242424; border: 1px solid #444444; padding: 5px; }
QMenu::item { padding: 9px 20px; border-radius: 4px; }
QMenu::item:selected { background: #383838; }
QMenu::separator { background: #3a3a3a; height: 1px; margin: 4px 8px; }
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
    result.setTextFormat(Qt.TextFormat.PlainText)
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
        self.decode_failures: set[str] = set()
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
        self.setWindowTitle(f"Ayikla {__version__} · Beta")
        self.setWindowIcon(app_icon())
        self.resize(1380, 900)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(STYLE)
        self._build_ui()
        if self.preferences.read_error:
            self.feedback.setText("Recent folders and window settings could not be read. Use Open folder to continue; "
                                  "check read permission for the app folder.")
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(180)
        self._resize_timer.timeout.connect(self._request_image)
        self.canvas.resized.connect(lambda: self._resize_timer.start())
        self.canvas.resized.connect(self._position_toast)
        self.canvas.activity.connect(self._reveal_overlays)
        self._restore_geometry()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 12, 20, 10)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(label("AYIKLA", "brand"))
        header.addSpacing(14)
        self.folder_label = ElidedLabel("From shoot to shortlist.")
        self.folder_label.setObjectName("muted")
        header.addWidget(self.folder_label, 1)
        self.folders_button = button("Folders", lambda: None, "ghost")
        self.folder_menu = QMenu(self)
        self.folder_actions = {}
        for name, title in (("", "Shoot folder"), (KEPT, "Kept photos · 01_secilen"),
                            (EDIT, "Edit picks · 02_edit"), (REJECTED, "Rejected photos · _red")):
            action = self.folder_menu.addAction(title)
            action.triggered.connect(lambda checked=False, value=name: self.open_shoot_folder(value))
            self.folder_actions[name] = action
            if not name:
                self.folder_menu.addSeparator()
        self.folders_button.setMenu(self.folder_menu)
        self.folders_button.setEnabled(False)
        header.addWidget(self.folders_button)
        self.open_button = button("Open folder", self.choose_folder, "ghost")
        self.open_button.setToolTip("Choose a shoot folder · Ctrl+O")
        header.addWidget(self.open_button)
        self.full_button = button("Full screen", self.toggle_fullscreen, "ghost")
        self.full_button.setToolTip("Full screen / window · F11")
        header.addWidget(self.full_button)
        help_button = button("Help  ·  H", self.toggle_help, "ghost")
        header.addWidget(help_button)
        for control in (self.folders_button, self.open_button, self.full_button, help_button):
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addLayout(header)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        welcome_page = QScrollArea()
        welcome_page.setFrameShape(QFrame.Shape.NoFrame)
        welcome_page.setWidgetResizable(True)
        welcome_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_content = QWidget()
        self.welcome_content.setMaximumWidth(740)
        intro = QVBoxLayout(self.welcome_content)
        intro.setContentsMargins(0, 12, 0, 12)
        intro.setSpacing(16)
        intro.addWidget(label("PHOTO CULLING  /  TWO ROUNDS", "eyebrow"))
        intro.addWidget(label("Find your best frames.\nBuild your shortlist.", "hero"))
        description = label("Open your shoot. Choose what to keep, then what to edit\n"
                            "in Lightroom. JPG and CR3 stay together.", "muted")
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px;")
        intro.addWidget(description)
        steps = QHBoxLayout()
        steps.setSpacing(12)
        for number, title, text in (("01", "Keep / Reject", "Keep → 01_secilen\nEle / Delete → _red"),
                                    ("02", "Edit / Lightroom", "E → copy into 02_edit\nReady to import into Lightroom")):
            card = QFrame()
            card.setObjectName("stepCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(7)
            card_layout.addWidget(label(number, "stepNumber"))
            card_layout.addWidget(label(title, "stepTitle"))
            card_layout.addWidget(label(text, "muted"))
            steps.addWidget(card, 1)
        intro.addLayout(steps)
        start = button("Choose a shoot folder", self.choose_folder, "primary")
        intro.addWidget(start, 0, Qt.AlignmentFlag.AlignLeft)
        intro.addWidget(label("Auto-saved  ·  Z to undo  ·  No files deleted", "muted"))
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(5)
        intro.addSpacing(2)
        intro.addLayout(self.recent_layout)
        self._update_recent()
        welcome_layout.addWidget(self.welcome_content)
        welcome_page.setWidget(welcome)
        self.pages.addWidget(welcome_page)

        gallery = QWidget()
        content = QVBoxLayout(gallery)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.cull_button = button("1  Keep / Reject", lambda: self.set_mode("cull"))
        self.edit_button = button("2  Edit / Lightroom  ·  M", lambda: self.set_mode("edit"))
        for control in (self.cull_button, self.edit_button):
            control.setCheckable(True)
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            toolbar.addWidget(control)
        toolbar.addStretch()
        self.counter = label("", "counter")
        toolbar.addWidget(self.counter)
        content.addLayout(toolbar)
        self.ignored_notice = label("", "muted")
        self.ignored_notice.hide()
        content.addWidget(self.ignored_notice)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        content.addWidget(self.progress)
        self.round_hint = label("", "muted")
        self.round_hint.setWordWrap(True)
        content.addWidget(self.round_hint)
        self.canvas = PhotoCanvas()
        self.viewer = QStackedWidget()
        self.viewer.addWidget(self.canvas)
        end_page = QScrollArea()
        end_page.setFrameShape(QFrame.Shape.NoFrame)
        end_page.setWidgetResizable(True)
        end_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_body = QWidget()
        end_body_layout = QVBoxLayout(end_body)
        end_body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        end_body_layout.setContentsMargins(12, 12, 12, 12)
        end_body_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_card = QFrame()
        self.end_card.setObjectName("summaryCard")
        self.end_card.setMinimumWidth(520)
        self.end_card.setMaximumWidth(620)
        end_layout = QVBoxLayout(self.end_card)
        end_layout.setContentsMargins(28, 24, 28, 24)
        end_layout.setSpacing(14)
        eyebrow = label("ROUND COMPLETE", "eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(eyebrow)
        title = label("Your shortlist is ready.", "summaryTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(title)
        self.end_counts = label("", "summaryCounts")
        self.end_counts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(self.end_counts)
        self.end_errors = QPlainTextEdit()
        self.end_errors.setReadOnly(True)
        self.end_errors.setMaximumHeight(96)
        self.end_errors.hide()
        end_layout.addWidget(self.end_errors)
        self.round2_button = button("Choose photos for editing  ·  M", lambda: self.set_mode("edit"), "primary")
        end_layout.addWidget(self.round2_button)
        self.explorer_button = button("Open 02_edit in Explorer", self.open_edit_folder)
        end_layout.addWidget(self.explorer_button)
        folder_links = QHBoxLayout()
        self.kept_folder_button = button("Kept photos  ↗", lambda: self.open_shoot_folder(KEPT), "ghost")
        self.rejected_folder_button = button("Rejected photos  ↗", lambda: self.open_shoot_folder(REJECTED), "ghost")
        folder_links.addWidget(self.kept_folder_button)
        folder_links.addWidget(self.rejected_folder_button)
        end_layout.addLayout(folder_links)
        end_layout.addWidget(button("Back to photos", self.return_to_photos, "ghost"))
        end_note = label("Decisions saved. Press Z to undo the last one.", "muted")
        end_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        end_layout.addWidget(end_note)
        end_body_layout.addWidget(self.end_card)
        end_page.setWidget(end_body)
        self.viewer.addWidget(end_page)
        content.addWidget(self.viewer, 1)
        self.filmstrip = Filmstrip()
        self.filmstrip.activated.connect(self.jump_to)
        content.addWidget(self.filmstrip)

        self.photo_info = QWidget()
        info = QHBoxLayout(self.photo_info)
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(7)
        self.filename = ElidedLabel()
        self.filename.setObjectName("filename")
        self.filename.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.filename.setMinimumWidth(120)
        self.filename.setMaximumWidth(280)
        info.addWidget(self.filename)
        self.raw_badge = label("", "badge")
        info.addWidget(self.raw_badge)
        self.edit_badge = label("PICKED FOR EDITING", "badge")
        self.edit_badge.setStyleSheet("color: #dedede; background: #363636;")
        info.addWidget(self.edit_badge)
        info.addStretch(1)
        self.remaining = label("", "muted")
        info.addWidget(self.remaining)
        self.current_folder_button = button("Open folder  ↗", self.open_current_folder, "ghost")
        self.zoom_button = button("100%  ·  F", self.toggle_zoom, "ghost")
        self.info_button = button("Info  ·  I", self.toggle_info, "ghost")
        self.strip_button = button("Filmstrip  ·  T", self.toggle_filmstrip, "ghost")
        info.addWidget(self.current_folder_button)
        for control in (self.zoom_button, self.info_button, self.strip_button):
            info.addWidget(control)
        for control in (self.current_folder_button, self.zoom_button, self.info_button, self.strip_button):
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        content.addWidget(self.photo_info)

        controls = QFrame()
        self.controls = controls
        controls.setObjectName("bar")
        actions = QHBoxLayout(controls)
        actions.setContentsMargins(8, 7, 8, 7)
        actions.setSpacing(6)
        self.reject_button = button("Reject  ·  Delete", lambda: self.decide(False), "reject")
        self.reject_button.setToolTip("Moves JPG + matching CR3 to _red. Z to undo; no files are deleted.")
        actions.addWidget(self.reject_button)
        actions.addStretch()
        self.previous_button = button("↑  Previous", lambda: self.navigate(-1), "ghost")
        self.next_button = button("Next  ↓", lambda: self.navigate(1), "ghost")
        self.next_button.setToolTip("Next photo without deciding · Space / ↓")
        actions.addWidget(self.previous_button)
        actions.addWidget(self.next_button)
        actions.addStretch()
        self.keep_button = button("Keep  ·  → / Enter", lambda: self.decide(True), "keep")
        self.keep_button.setToolTip("Moves JPG + matching CR3 to 01_secilen for keeping.")
        actions.addWidget(self.keep_button)
        self.mark_button = button("Pick for editing  ·  E", self.toggle_edit, "keep")
        self.mark_button.setToolTip("Copies JPG + matching CR3 to 02_edit for Lightroom.")
        actions.addWidget(self.mark_button)
        self.summary_button = button("Round summary", self.show_summary)
        actions.addWidget(self.summary_button)
        content.addWidget(controls)
        self.pages.addWidget(gallery)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.undo_button = button("Undo  ·  Z", self.undo, "ghost")
        footer.addWidget(self.undo_button)
        self.feedback = label("Choose a shoot folder to start.", "muted")
        self.feedback.setWordWrap(True)
        footer.addWidget(self.feedback, 1)
        self.retry_button = button("Retry", self.retry, "ghost")
        self.retry_button.hide()
        footer.addWidget(self.retry_button)
        footer.addWidget(label("Auto-save", "muted"))
        layout.addLayout(footer)
        self.undo_button.setEnabled(False)
        self.setCentralWidget(root)
        self.toast = FadingOverlay(root)
        self.canvas.help.setParent(root)
        self.canvas.help.hide()

    def _update_recent(self):
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.preferences.recent:
            self.recent_layout.addWidget(label("RECENT FOLDERS", "muted"))
        for path in self.preferences.recent:
            control = button(Path(path).name, lambda checked=False, value=path: self.open_folder(value), "recent")
            control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
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
        path = QFileDialog.getExistingDirectory(self, "Choose a shoot folder",
                                               str(self.session.root) if self.session else "")
        if path:
            self.open_folder(path)

    def open_folder(self, path: str | Path):
        if self.busy:
            return
        if self.session and Path(path).resolve() == self.session.root:
            self.refresh()
            return
        self._run(lambda: ShootSession(path), "Opening shoot and journal…", "Shoot ready.", opening=True)

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
        self.decode_failures.clear()
        self.preview_photo = None
        self.summary_requested = False
        self.zoomed = False
        self.canvas.set_zoom(False)
        self.cache.clear()
        self.folder_label.setText(self.session.root.name)
        self.folder_label.setToolTip(str(self.session.root))
        self.setWindowTitle(f"{self.session.root.name} — Ayikla {__version__} · Beta")
        self.mode = self.session.view["mode"]
        self.pages.setCurrentIndex(1)
        recovered = self.session.recovery_count
        self.feedback.setText("Interrupted operation recovered." if recovered else self._success)
        try:
            self.preferences.add_recent(self.session.root)
            self._update_recent()
        except OSError:
            self.feedback.setText("Recent folder could not be saved. Check write permission for the app folder.")
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
            message += "\nJournal write could not be verified. Resolve the disk problem and reopen the app."
        elif self.session and self.session.pending_id:
            message += "\nThe operation is incomplete. Resolve the destination conflict or disk problem, then press Retry."
        self.feedback.setText(message)
        self._update_enabled()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Operation could not be completed")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.button(QMessageBox.StandardButton.Ok).setText("OK")
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
            self.ignored_notice.setText(self.session.ignored_notice)
            self.ignored_notice.setVisible(bool(self.session.ignored_notice))
            self.photos = snapshot.pending if self.mode == "cull" else snapshot.kept
            self.index = next((i for i, photo in enumerate(self.photos) if photo.key == preferred), 0)
            if allow_preview and preferred and not any(photo.key == preferred for photo in self.photos):
                self.preview_photo = next((photo for photo in self.session.all_photos() if photo.key == preferred), None)
            if self.mode == "cull":
                self.round_hint.setText("ROUND 1 · KEEP OR REJECT: Keep → 01_secilen · Reject / Delete → _red "
                                        "(Z to undo) · Decisions are saved automatically.")
                position = len(snapshot.kept) + len(snapshot.rejected) + self.index + 1 if self.photos else snapshot.total
                self.counter.setText(f"{position} / {snapshot.total}  ·  {len(snapshot.kept)} kept  ·  {len(snapshot.rejected)} rejected")
                self.remaining.setText(f"{len(snapshot.pending)} undecided")
            else:
                self.round_hint.setText("ROUND 2 · EDIT / LIGHTROOM: E → copy JPG + matching CR3 to 02_edit · "
                                        "E again: remove edit pick · Decisions are saved automatically.")
                position = self.index + 1 if self.photos else 0
                self.counter.setText(f"{position} / {len(snapshot.kept)}  ·  {len(self.session.edits)} picked for editing")
                self.remaining.setText("01_secilen → 02_edit · copy")
            self.progress.setRange(0, max(snapshot.total, 1))
            self.progress.setValue(len(snapshot.kept) + len(snapshot.rejected))
            self.cull_button.setChecked(self.mode == "cull")
            self.edit_button.setChecked(self.mode == "edit")
            photo = self.current
            self.canvas.image = QImage()
            if photo:
                self.filename.setText(photo.jpeg.name)
                self.raw_badge.setText("JPG + CR3" if photo.raw else "⚠ No matching CR3")
                self.raw_badge.setStyleSheet("" if photo.raw else "color: #cccccc; background: #303030;")
                self.raw_badge.show()
                self.edit_badge.setVisible(photo.key in self.session.edits)
                self.mark_button.setText("Remove edit pick  ·  E" if photo.key in self.session.edits else "Pick for editing  ·  E")
                self.canvas.message = "Loading…"
                self.session.save_view(self.mode, photo.key)
                self._request_image()
                self.viewer.setCurrentIndex(0)
                if self.preview_photo:
                    self.counter.setText(f"{photo.jpeg.name}  ·  {'rejected photo · preview' if photo.state == 'rejected' else 'preview'}")
            else:
                self.cache.clear()
                self.filename.setText("Round 1 complete" if self.mode == "cull" and snapshot.total else "No photos")
                if self.summary_requested:
                    self.filename.setText("Round 2 summary")
                    self.counter.setText("Round summary")
                self.raw_badge.hide()
                self.edit_badge.hide()
                if self.mode == "cull":
                    self.canvas.message = ("Culling complete.\nPress M to choose photos for editing."
                                           if snapshot.total else "No JPG/JPEG photos found in this folder.")
                else:
                    self.canvas.message = "No kept photos yet.\nPress Right or Enter in round 1 to keep photos."
                self.session.save_view(self.mode, None)
                self.viewer.setCurrentIndex(1 if snapshot.total and (self.mode == "cull" or self.summary_requested) else 0)
            self.end_counts.setText(f"{snapshot.total} total  ·  {len(snapshot.kept)} kept  ·  "
                                    f"{len(snapshot.rejected)} rejected\n{len(self.session.edits)} picked for editing")
            for name, title, count in ((KEPT, "Kept photos", len(snapshot.kept)),
                                       (EDIT, "Edit picks", len(self.session.edits)),
                                       (REJECTED, "Rejected photos", len(snapshot.rejected))):
                self.folder_actions[name].setText(f"{title} · {name}  ({count})")
            self._update_decode_summary()
            self.round2_button.setEnabled(bool(snapshot.kept))
            self.filmstrip.set_items(self.session.all_photos(), photo.key if photo else None, self.session.edits)
            self._update_overlays()
            self.canvas.update()
            self._update_enabled()
            QTimer.singleShot(0, self._position_toast)
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
            if error:
                self.decode_failures.add(self.current.key)
            else:
                self.decode_failures.discard(self.current.key)
            self.canvas.message = (f"Could not open JPEG.\n{self.current.jpeg.name}\n{error}\n"
                                   "Press Enter to keep or Delete / X to reject this file.") if error else ""
            self._update_decode_summary()
            self.canvas.update()

    def _update_decode_summary(self):
        paths = [photo.jpeg.relative_to(self.session.root).as_posix()
                 for photo in self.session.all_photos() if photo.key in self.decode_failures]
        self.end_errors.setPlainText("JPEGs that could not be opened in this session "
                                     f"({len(paths)}):\n" + "\n".join(paths) if paths else "")
        self.end_errors.setVisible(bool(paths))

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
        self.folders_button.setEnabled(self.session is not None and not self.busy)
        self.current_folder_button.setEnabled(has_photo)
        for control in (self.kept_folder_button, self.rejected_folder_button, self.explorer_button):
            control.setEnabled(enabled)
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
        summary_visible = self.viewer.currentIndex() == 1
        self.controls.setVisible(not summary_visible)
        self.photo_info.setVisible(not summary_visible)
        self.remaining.setVisible(self.width() >= 1180)

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
        self._run(lambda: self.session.decide(photo, keep, next_key), "Moving files…",
                  "Kept" if keep else "Rejected")

    def toggle_edit(self):
        if not self.current or self.mode != "edit" or not self.session or self.preview_photo:
            return
        photo = self.current
        marked = photo.key in self.session.edits
        self._run(lambda: self.session.toggle_edit(photo), "Saving edit pick…",
                  "Edit pick removed; copies archived" if marked else "Picked for editing")

    def undo(self):
        if self.session and self.session.stack:
            self._run(self.session.undo, "Undoing the last decision…", "Undone")

    def retry(self):
        if self.session:
            self._needs_metadata_rescan = True
            self._run(self.session.recover_pending, "Checking folder and interrupted operation…", "Folder refreshed")

    def notify(self, message):
        self.toast.reveal(message)
        self._position_toast()

    def _position_toast(self):
        origin = self.viewer.mapTo(self.centralWidget(), QPoint(0, 0))
        horizontal = 12 if self.viewer.currentIndex() == 1 else max(8, (self.viewer.width() - self.toast.width()) // 2)
        self.toast.move(origin.x() + horizontal,
                        origin.y() + max(8, self.viewer.height() - self.toast.height() - 18))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self._position_toast()
            self.canvas.position_overlays()
            self.remaining.setVisible(self.width() >= 1180)

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
            self.canvas.info.reveal(info.text() if info else f"{self.current.jpeg.name}\nReading EXIF…")
            self.canvas.position_overlays()

    def toggle_help(self):
        if self.canvas.help.isVisible():
            self.canvas.help.dismiss()
        else:
            self.canvas.help.reveal(f"KEYBOARD · AYIKLA {__version__} · BETA\n\nROUND 1 · KEEP OR REJECT\n→ / Enter   Keep → 01_secilen\n"
                                    "← / X / Delete   Reject → _red (no files deleted)\n\n"
                                    "ROUND 2 · EDIT / LIGHTROOM\nE   copy to 02_edit / remove edit pick\n\n"
                                    "Decisions are saved automatically.\n"
                                    "Space / ↓   Next     ↑   Previous\nZ   Undo     M   Switch round\n"
                                    "F   100% / Fit     Drag   Pan\nI   Photo info     T   Filmstrip\n"
                                    "H / ?   Help     Esc   Close help / leave zoom\nF11   Full screen     Ctrl+O   Open folder",
                                    auto_fade=False)
            self.canvas.position_overlays()

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
        parts = ([f"Burst {hint[0]}/{hint[1]}"] if hint else []) + (["100% · drag to pan · F to fit"] if self.zoomed else [])
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
        self.open_shoot_folder(EDIT)

    def open_current_folder(self):
        if self.current and self.session:
            relative = self.current.jpeg.parent.relative_to(self.session.root)
            self.open_shoot_folder("" if relative == Path(".") else relative.as_posix())

    def open_shoot_folder(self, name=""):
        if not self.session or self.busy:
            return
        try:
            if name not in {"", KEPT, EDIT, REJECTED}:
                raise AyiklaError("Only folders inside this shoot can be opened.")
            path = self.session._path(name) if name else self.session.root
            path.mkdir(exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise OSError(f"Could not open Explorer. Open this folder manually: {path}")
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
        elif self.mode == "cull" and key in (Qt.Key.Key_Left, Qt.Key.Key_X, Qt.Key.Key_Delete):
            self.decide(False)
        elif self.mode == "edit" and key == Qt.Key.Key_E:
            self.toggle_edit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.busy:
            self.feedback.setText("A file operation is running. Close the window once it finishes.")
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
            self.feedback.setText("Window settings could not be saved. Check write permission for the app folder.")
        if self.session:
            self.session.close()
        event.accept()
