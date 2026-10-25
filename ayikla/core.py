"""Filesystem operations and a durable, append-only write-ahead journal.

The UI is intentionally absent here. Every path is relative to one shoot root.
There are no deletion calls. Unmarking copies moves them into a private archive.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path, PurePosixPath

KEPT = "01_secilen"
EDIT = "02_edit"
REJECTED = "_red"
ARCHIVE = ".ayikla_saklanan"
LOG = "ayikla_log.jsonl"
VERSION = 1


class AyiklaError(Exception):
    """A recoverable error that can be shown to the user."""


class ConflictError(AyiklaError):
    pass


class RecoveryError(AyiklaError):
    pass


@dataclass(frozen=True)
class Photo:
    key: str
    jpeg: Path
    raw: Path | None
    state: str

    @property
    def files(self) -> tuple[Path, ...]:
        return (self.jpeg, self.raw) if self.raw else (self.jpeg,)


@dataclass(frozen=True)
class Snapshot:
    pending: tuple[Photo, ...]
    kept: tuple[Photo, ...]
    rejected: tuple[Photo, ...]

    @property
    def total(self) -> int:
        return len(self.pending) + len(self.kept) + len(self.rejected)


def natural_key(value: str) -> list:
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", value)]


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def pair_photos(folder: Path, state: str = "pending") -> tuple[Photo, ...]:
    """Pair immediate JPEG/CR3 children by case-insensitive stem, never recurse."""
    if not folder.exists():
        return ()
    if is_link(folder) or not folder.is_dir():
        raise ConflictError(f"Normal bir klasör gerekli: {folder}")
    groups: dict[str, dict[str, list[Path]]] = {}
    for path in folder.iterdir():
        extension = path.suffix.casefold()
        if extension not in {".jpg", ".jpeg", ".cr3"}:
            continue
        if is_link(path):
            raise ConflictError(f"Bağlantı olan fotoğraf işlenmez: {path.name}")
        if not path.is_file():
            continue
        group = groups.setdefault(path.stem.casefold(), {"jpeg": [], "raw": []})
        group["raw" if extension == ".cr3" else "jpeg"].append(path)
    photos = []
    for key, group in groups.items():
        if not group["jpeg"]:
            continue
        if len(group["jpeg"]) != 1 or len(group["raw"]) > 1:
            raise ConflictError(f"Aynı gövde adına sahip birden fazla dosya var: {key}")
        photos.append(Photo(key, group["jpeg"][0],
                            group["raw"][0] if group["raw"] else None, state))
    return tuple(sorted(photos, key=lambda photo: natural_key(photo.jpeg.name)))


def fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "device": stat.st_dev, "inode": stat.st_ino}


def same_file(path: Path, expected: dict) -> bool:
    return path.is_file() and not is_link(path) and fingerprint(path) == expected


def rescan_on_conflict(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (ConflictError, FileNotFoundError):
            try:
                self.rescan()
            except (AyiklaError, OSError):
                pass  # Keep the original conflict and the last valid index.
            raise
    return guarded


def move_no_replace(source: Path, target: Path) -> None:
    """Windows rename with no REPLACE_EXISTING, including the race after preflight."""
    if os.path.lexists(target):
        raise FileExistsError(f"Hedef zaten var: {target}")
    if sys.platform != "win32":
        raise AyiklaError("Ayikla'nın güvenli taşıma motoru Windows gerektirir.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move = kernel32.MoveFileExW
    move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move.restype = ctypes.c_int
    # WRITE_THROUGH, without COPY_ALLOWED or REPLACE_EXISTING. No cross-volume move.
    if not move(str(source), str(target), 0x8):
        raise ctypes.WinError(ctypes.get_last_error())


class ShootSession:
    """One locked shoot. Close explicitly, or use as a context manager."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise AyiklaError("Bir çekim klasörü seç.")
        self._lock = None
        self._log = None
        self.transactions: dict[str, dict] = {}
        self.receipts: dict[str, dict[int, dict]] = {}
        self.committed: set[str] = set()
        self.stack: list[str] = []
        self.edits: dict[str, str] = {}
        self.view: dict[str, str | None] = {"mode": "cull", "key": None}
        self.pending_id: str | None = None
        self.recovery_count = 0
        self.faulted = False
        self._photos: dict[str, Photo] | None = None
        self._order: tuple[str, ...] = ()
        self._snapshot: Snapshot | None = None
        try:
            for name in (KEPT, EDIT, REJECTED, ARCHIVE, LOG, ".ayikla.lock"):
                self._path(name)
            self._acquire_lock()
            self._log = (self.root / LOG).open("a+b", buffering=0)
            self._load_log()
            if self.pending_id:
                self.recover_pending()
            self.rescan()  # One filesystem scan on open, after journal recovery.
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        if self._log:
            self._log.close()
            self._log = None
        if self._lock:
            self._lock.close()  # Closing releases the OS lock even after an exception.
            self._lock = None

    def _path(self, relative: str) -> Path:
        rel = PurePosixPath(relative)
        if (not relative or rel.is_absolute() or ".." in rel.parts
                or "\\" in relative or ":" in relative):
            raise ConflictError(f"Günlükte geçersiz yol: {relative}")
        result = self.root.joinpath(*rel.parts)
        if result == self.root or not result.resolve().is_relative_to(self.root):
            raise ConflictError(f"Çekim klasörü dışında yol: {relative}")
        for part in (result, *result.parents):
            if part == self.root:
                break
            if is_link(part):
                raise ConflictError(f"Dosya/klasör bağlantısı işlenmez: {relative}")
        return result

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _existing(self, path: Path) -> Path | None:
        """Check case-insensitively as well as catching dangling links."""
        if sys.platform == "win32":
            # Windows already resolves file names case-insensitively. No need to
            # enumerate a growing target directory before every file operation.
            return path if os.path.lexists(path) else None
        if not path.parent.exists():
            return None
        for entry in path.parent.iterdir():
            if entry.name.casefold() == path.name.casefold():
                return entry
        return None

    def _acquire_lock(self) -> None:
        if sys.platform != "win32":
            raise AyiklaError("Bu sürüm Windows içindir.")
        import msvcrt
        self._lock = (self.root / ".ayikla.lock").open("a+b")
        if self._lock.seek(0, os.SEEK_END) == 0:
            self._lock.write(b"\0")
            self._lock.flush()
        self._lock.seek(0)
        try:
            msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ConflictError("Bu çekim başka bir Ayikla penceresinde açık.") from error

    def _append(self, record: dict) -> None:
        assert self._log is not None
        payload = {"v": VERSION, "time": datetime.now(timezone.utc).isoformat(), **record}
        try:
            self._log.seek(0, os.SEEK_END)
            data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            if self._log.write(data) != len(data):
                raise OSError("Günlük diske tam yazılamadı.")
            self._log.flush()
            os.fsync(self._log.fileno())
        except OSError:
            # A failed flush has an uncertain outcome. Reopening and replaying is
            # the only safe way to establish what actually reached the journal.
            self.faulted = True
            raise

    def _load_log(self) -> None:
        assert self._log is not None
        self._log.seek(0)
        data = self._log.read()
        # Repair a torn last append without truncating or losing its original bytes.
        if data and not data.endswith(b"\n"):
            self._log.seek(0, os.SEEK_END)
            self._log.write(b"\n")
            os.fsync(self._log.fileno())
        lines = data.splitlines()
        invalid = object()
        parsed = []
        for line in lines:
            try:
                parsed.append(json.loads(line) if line else invalid)
            except (ValueError, UnicodeDecodeError):
                parsed.append(invalid)
        for number, line in enumerate(lines, 1):
            if not line:
                continue
            record = parsed[number - 1]
            if record is invalid:
                repaired = any(isinstance(later, dict) and later.get("type") == "repair"
                               and later.get("line") == number
                               and later.get("fragment_hex") == line.hex()
                               for later in parsed[number:])
                if not repaired:
                    # Also tolerate a second crash partway through writing a repair.
                    # Unrepaired corruption before a later real operation is fatal.
                    later_operation = any(later is not invalid and
                                          (not isinstance(later, dict) or later.get("type") != "repair")
                                          for later in parsed[number:])
                    if later_operation:
                        raise RecoveryError(f"Günlük satırı okunamıyor ({number}). Dosyalara dokunulmadı.")
                    self._append({"type": "repair", "line": number, "fragment_hex": line.hex()})
                continue
            try:
                self._replay(record)
            except (KeyError, TypeError, ValueError, IndexError) as error:
                raise RecoveryError(f"Günlük yapısı geçersiz ({number}).") from error

    def _replay(self, record: dict) -> None:
        if not isinstance(record, dict) or record.get("v") != VERSION:
            raise RecoveryError("Desteklenmeyen günlük sürümü.")
        kind = record["type"]
        if kind == "begin":
            if self.pending_id or record["id"] in self.transactions:
                raise RecoveryError("Günlükte çakışan işlem var.")
            if record["action"] not in {"keep", "reject", "edit_mark", "edit_unmark", "undo"}:
                raise RecoveryError("Günlükte bilinmeyen karar var.")
            for operation in record["ops"]:
                if operation["kind"] not in {"move", "copy"}:
                    raise RecoveryError("Günlükte bilinmeyen dosya işlemi var.")
                self._path(operation["src"])
                self._path(operation["dst"])
                if operation["kind"] == "copy":
                    self._path(operation["stage"])
            self.transactions[record["id"]] = record
            self.receipts[record["id"]] = {}
            self.pending_id = record["id"]
        elif kind == "ready":
            if record["id"] != self.pending_id:
                raise RecoveryError("Günlükte sahipsiz kopya kaydı var.")
            self.receipts[record["id"]][record["index"]] = record["fingerprint"]
        elif kind == "commit":
            if record["id"] != self.pending_id:
                raise RecoveryError("Günlükte sahipsiz tamamlanma kaydı var.")
            self._apply_commit(record["id"])
        elif kind == "view":
            self.view = self._validate_view(record["view"])
        elif kind != "repair":
            raise RecoveryError("Günlükte bilinmeyen kayıt var.")

    @staticmethod
    def _validate_view(view: dict) -> dict:
        if view.get("mode") not in {"cull", "edit"}:
            raise RecoveryError("Günlükte tur bilgisi geçersiz.")
        if view.get("key") is not None and not isinstance(view["key"], str):
            raise RecoveryError("Günlükte fotoğraf bilgisi geçersiz.")
        return dict(view)

    def _apply_commit(self, transaction_id: str) -> None:
        tx = self.transactions[transaction_id]
        action, key = tx["action"], tx["key"]
        if action == "undo":
            if not self.stack or self.stack[-1] != tx["undo_of"]:
                raise RecoveryError("Geri alma sırası geçersiz.")
            target = self.transactions[self.stack.pop()]
            if target["action"] == "edit_mark":
                self.edits.pop(key, None)
            elif target["action"] == "edit_unmark":
                self.edits[key] = target["mark_id"]
        else:
            self.stack.append(transaction_id)
            if action == "edit_mark":
                self.edits[key] = transaction_id
            elif action == "edit_unmark":
                self.edits.pop(key, None)
        self.committed.add(transaction_id)
        self.view = self._validate_view(tx["view_after"])
        self.pending_id = None
        if self._photos is not None:
            effective = self.transactions[tx["undo_of"]]["action"] if action == "undo" else action
            if effective in {"keep", "reject"}:
                state = "pending" if action == "undo" else ("kept" if action == "keep" else "rejected")
                paths = [self._path(op["dst"]) for op in tx["ops"]]
                jpeg = next(path for path in paths if path.suffix.casefold() in {".jpg", ".jpeg"})
                raw = next((path for path in paths if path.suffix.casefold() == ".cr3"), None)
                self._photos[key] = Photo(key, jpeg, raw, state)
                self._snapshot = None

    def rescan(self) -> Snapshot:
        """Explicit refresh on open, Retry or conflict; publish only a valid scan."""
        result = Snapshot(pair_photos(self.root), pair_photos(self.root / KEPT, "kept"),
                          pair_photos(self.root / REJECTED, "rejected"))
        seen: set[str] = set()
        for photo in (*result.pending, *result.kept, *result.rejected):
            if photo.key in seen:
                raise ConflictError(f"Aynı fotoğraf birden fazla klasörde: {photo.jpeg.name}")
            seen.add(photo.key)
        photos = (*result.pending, *result.kept, *result.rejected)
        self._photos = {photo.key: photo for photo in photos}
        self._order = tuple(photo.key for photo in sorted(photos, key=lambda item: natural_key(item.jpeg.name)))
        self._snapshot = result
        return result

    def snapshot(self) -> Snapshot:
        """Immutable in-memory view. No directory enumeration or filesystem reads."""
        if self._snapshot is None:
            assert self._photos is not None
            photos = tuple(self._photos[key] for key in self._order)
            self._snapshot = Snapshot(*(tuple(photo for photo in photos if photo.state == state)
                                        for state in ("pending", "kept", "rejected")))
        return self._snapshot

    def all_photos(self) -> tuple[Photo, ...]:
        assert self._photos is not None
        return tuple(self._photos[key] for key in self._order)

    def save_view(self, mode: str, key: str | None) -> None:
        self._ensure_ready()
        view = self._validate_view({"mode": mode, "key": key})
        if self.view != view:
            self._append({"type": "view", "view": view})
            self.view = view

    def _ensure_ready(self) -> None:
        if self._log is None:
            raise AyiklaError("Çekim kapalı.")
        if self.faulted:
            raise RecoveryError("Günlük diske yazılamadı. Disk sorununu giderip uygulamayı yeniden aç.")
        if self.pending_id:
            raise RecoveryError("Yarım kalan işlem var. Önce Yeniden dene düğmesine bas.")

    def _move_op(self, source: Path, target: Path, expected: dict | None = None) -> dict:
        self._path(self._relative(source))
        self._path(self._relative(target))
        if expected is not None and not same_file(source, expected):
            raise ConflictError(f"Dosya dışarıdan değişmiş veya kayıp: {source.name}")
        return {"kind": "move", "src": self._relative(source),
                "dst": self._relative(target), "fingerprint": fingerprint(source)}

    def _preflight(self, operations: list[dict]) -> None:
        destinations: set[str] = set()
        for op in operations:
            source, target = self._path(op["src"]), self._path(op["dst"])
            if not same_file(source, op["fingerprint"]):
                raise ConflictError(f"Kaynak dosya değişmiş veya kayıp: {source.name}")
            if self._existing(target) is not None:
                raise ConflictError(f"Hedef zaten var; üzerine yazılmadı: {op['dst']}")
            if op["dst"].casefold() in destinations:
                raise ConflictError("İşlemde aynı hedef iki kez var.")
            destinations.add(op["dst"].casefold())
            for parent in target.parents:
                if parent == self.root:
                    break
                if parent.exists() and not parent.is_dir():
                    raise ConflictError(f"Hedef klasör yolu bir dosya: {parent.name}")

    def _transaction(self, action: str, key: str, operations: list[dict],
                     view_after: dict, transaction_id: str | None = None, **extra) -> None:
        self._ensure_ready()
        self._validate_view(view_after)
        self._preflight(operations)  # Check *both* JPG and RAW before moving either.
        record = {"type": "begin", "id": transaction_id or uuid.uuid4().hex,
                  "action": action, "key": key, "ops": operations,
                  "view_before": dict(self.view), "view_after": view_after, **extra}
        self._append(record)
        self._replay({"v": VERSION, **record})
        self._finish_pending()

    def _finish_move(self, operation: dict) -> None:
        source, target = self._path(operation["src"]), self._path(operation["dst"])
        existing = self._existing(target)
        if source.exists():
            if existing is not None:
                raise ConflictError(f"Hedef zaten var: {operation['dst']}")
            if not same_file(source, operation["fingerprint"]):
                raise ConflictError(f"Dosya değişmiş: {operation['src']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            move_no_replace(source, target)
        elif existing is None or not same_file(target, operation["fingerprint"]):
            raise RecoveryError(f"Taşınan dosya doğrulanamadı: {operation['dst']}")

    def _finish_copy(self, transaction_id: str, index: int, operation: dict) -> None:
        source, target = self._path(operation["src"]), self._path(operation["dst"])
        stage = self._path(operation["stage"])
        receipt = self.receipts[transaction_id].get(index)
        if receipt is None:
            if self._existing(target) is not None:
                raise ConflictError(f"Kopya hedefi zaten var: {operation['dst']}")
            if not same_file(source, operation["fingerprint"]):
                raise ConflictError(f"Kopyalanacak kaynak değişmiş: {operation['src']}")
            if self._existing(stage) is not None:
                # Preserve a partial copy left before a crash; never delete it.
                saved = self._path(f"{ARCHIVE}/yarim/{uuid.uuid4().hex}/{stage.name}")
                saved.parent.mkdir(parents=True, exist_ok=True)
                move_no_replace(stage, saved)
            stage.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as input_file, stage.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
                output_file.flush()
                os.fsync(output_file.fileno())
            if not same_file(source, operation["fingerprint"]):
                raise ConflictError(f"Kaynak kopyalama sırasında değişmiş: {source.name}")
            shutil.copystat(source, stage)
            receipt = fingerprint(stage)
            self._append({"type": "ready", "id": transaction_id, "index": index,
                          "fingerprint": receipt})
            self.receipts[transaction_id][index] = receipt
        self._finish_move({"kind": "move", "src": operation["stage"],
                           "dst": operation["dst"], "fingerprint": receipt})

    def _finish_pending(self) -> None:
        if not self.pending_id:
            return
        transaction_id = self.pending_id
        for index, operation in enumerate(self.transactions[transaction_id]["ops"]):
            if operation["kind"] == "move":
                self._finish_move(operation)
            else:
                self._finish_copy(transaction_id, index, operation)
        self._append({"type": "commit", "id": transaction_id})
        self._apply_commit(transaction_id)

    def recover_pending(self) -> None:
        if self.faulted:
            raise RecoveryError("Günlük hatasından sonra uygulamayı yeniden aç.")
        if self.pending_id:
            self._finish_pending()
            self.recovery_count += 1
        if self._photos is not None:
            self.rescan()

    @rescan_on_conflict
    def decide(self, photo: Photo, keep: bool, next_key: str | None = None) -> None:
        self._ensure_ready()
        current = self._photos.get(photo.key)
        if current is None or current != photo or current.state != "pending":
            raise ConflictError("Fotoğraf artık başlangıç klasöründe değil. Klasörü yeniden aç.")
        if photo.raw is None and photo.jpeg.with_suffix(".CR3").exists():
            raise ConflictError("Yeni bir CR3 bulundu. Yeniden dene ile klasörü tara ve kararını tekrar ver.")
        target = self.root / (KEPT if keep else REJECTED)
        operations = [self._move_op(path, target / path.name) for path in photo.files]
        self._transaction("keep" if keep else "reject", photo.key, operations,
                          {"mode": "cull", "key": next_key})

    @rescan_on_conflict
    def toggle_edit(self, photo: Photo) -> bool:
        self._ensure_ready()
        current = self._photos.get(photo.key)
        if current is None or current != photo or current.state != "kept":
            raise ConflictError("Yalnızca 01_secilen içindeki fotoğraflar düzenlemeye ayrılır.")
        transaction_id = uuid.uuid4().hex
        view = {"mode": "edit", "key": photo.key}
        if photo.key in self.edits:
            mark_id = self.edits[photo.key]
            mark = self.transactions[mark_id]
            operations = [self._move_op(self._path(op["dst"]),
                          self._path(f"{ARCHIVE}/kaldirilan/{transaction_id}/{Path(op['dst']).name}"),
                          self.receipts[mark_id][index])
                          for index, op in enumerate(mark["ops"])]
            self._transaction("edit_unmark", photo.key, operations, view,
                              transaction_id, mark_id=mark_id)
            return False
        operations = [{"kind": "copy", "src": self._relative(path),
                       "dst": f"{EDIT}/{path.name}",
                       "stage": f"{ARCHIVE}/islem/{transaction_id}/{path.name}.part",
                       "fingerprint": fingerprint(path)} for path in photo.files]
        self._transaction("edit_mark", photo.key, operations, view, transaction_id)
        return True

    @rescan_on_conflict
    def undo(self) -> bool:
        self._ensure_ready()
        if not self.stack:
            return False
        target_id = self.stack[-1]
        target = self.transactions[target_id]
        transaction_id = uuid.uuid4().hex
        operations = []
        for index, op in reversed(list(enumerate(target["ops"]))):
            source = self._path(op["dst"])
            if op["kind"] == "move":
                destination, expected = self._path(op["src"]), op["fingerprint"]
            else:
                destination = self._path(f"{ARCHIVE}/geri_alinan/{transaction_id}/{source.name}")
                expected = self.receipts[target_id][index]
            operations.append(self._move_op(source, destination, expected))
        self._transaction("undo", target["key"], operations, target["view_before"],
                          transaction_id, undo_of=target_id)
        return True
