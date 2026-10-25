"""Create the app's simple vector-derived Windows icon locally."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from ayikla.ui import app_icon

app = QApplication(sys.argv)
path = Path(__file__).resolve().parents[1] / "assets" / "ayikla.ico"
path.parent.mkdir(exist_ok=True)
if not app_icon().pixmap(128, 128).save(str(path), "ICO"):
    raise SystemExit("Could not create icon")
