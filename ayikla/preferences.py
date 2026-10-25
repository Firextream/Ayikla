"""Append-only portable preferences. No registry, AppData, rewriting or deletion."""

import json
import os
import sys
from pathlib import Path


class Preferences:
    def __init__(self, directory: str | Path | None = None):
        default = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        self.directory = Path(directory or os.environ.get("AYIKLA_STATE_DIR", default))
        self.path = self.directory / "ayikla_settings.jsonl"
        self.recent: list[str] = []
        self.window: dict = {}
        self.read_error = False
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            data = b""
        except OSError:
            # Portable settings may be unreadable on another computer. They are
            # optional; never let them prevent opening a shoot and its journal.
            self.read_error = True
            data = b""
        for line in data.splitlines():
            try:
                self._apply(json.loads(line))
            except (ValueError, TypeError, KeyError, UnicodeDecodeError):
                continue  # Preferences never affect the shoot journal's recovery.

    def _apply(self, record: dict):
        if not isinstance(record, dict) or record.get("v") != 1:
            return
        if record.get("type") == "recent" and isinstance(record.get("path"), str):
            path = record["path"]
            self.recent = [path] + [item for item in self.recent if item.casefold() != path.casefold()]
            self.recent = self.recent[:5]
        elif record.get("type") == "window":
            geometry = record.get("geometry")
            if (isinstance(geometry, list) and len(geometry) == 4
                    and all(isinstance(value, int) for value in geometry)
                    and 640 <= geometry[2] <= 16000 and 400 <= geometry[3] <= 16000):
                self.window = {"geometry": geometry, "fullscreen": bool(record.get("fullscreen")),
                               "maximized": bool(record.get("maximized"))}

    def _append(self, record: dict):
        if sys.platform != "win32":
            raise OSError("Bu sürüm Windows içindir.")
        import msvcrt
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"v": 1, **record}
        with self.path.open("a+b", buffering=0) as stream:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                end = stream.seek(0, os.SEEK_END)
                prefix = b""
                if end:
                    stream.seek(-1, os.SEEK_END)
                    prefix = b"\n" if stream.read(1) != b"\n" else b""
                stream.seek(0, os.SEEK_END)
                payload = prefix + (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
                if stream.write(payload) != len(payload):
                    raise OSError("Ayar günlüğü tam yazılamadı.")
                os.fsync(stream.fileno())
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        self._apply(record)

    def add_recent(self, path: str | Path):
        resolved = str(Path(path).resolve())
        if not self.recent or self.recent[0].casefold() != resolved.casefold():
            self._append({"type": "recent", "path": resolved})

    def save_window(self, geometry: list[int], fullscreen: bool, maximized: bool):
        values = {"geometry": geometry, "fullscreen": fullscreen, "maximized": maximized}
        if self.window != values:
            self._append({"type": "window", **values})
