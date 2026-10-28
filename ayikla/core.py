"""Filesystem operations and a durable, append-only write-ahead journal.

The UI is intentionally absent here. Every path is relative to one shoot root.
There are no deletion calls. Unmarking copies moves them into a private archive.
"""

from __future__ import annotations

import ctypes
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path, PurePosixPath

from .file_access import file_guard

KEPT = "01_secilen"
EDIT = "02_edit"
REJECTED = "_red"
ARCHIVE = ".ayikla_saklanan"
LOG = "ayikla_log.jsonl"
VERSION = 1
PREVIEW_EXTENSIONS = frozenset({".jpg", ".jpeg", ".tif", ".tiff"})
RAW_EXTENSIONS = frozenset({".cr3", ".cr2", ".crw", ".raf", ".arw", ".srf", ".sr2",
                            ".orf", ".nef", ".nrw", ".rw2", ".rwl", ".pef", ".dng", ".srw"})


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


def ignored_file_reason(path: Path) -> str | None:
    """Exclude metadata and Windows hidden/system files before pairing."""
    name = path.name.casefold()
    if name.startswith("._"):
        return "appledouble"
    if name in {"thumbs.db", "desktop.ini", ".ds_store"}:
        return "metadata"
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    if attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM):
        return "hidden_system"
    return None


def pair_photos(folder: Path, state: str = "pending", *,
                ignored: dict[str, int] | None = None) -> tuple[Photo, ...]:
    """Pair JPEG/RAW or accept standalone JPEG/TIFF; never recurse."""
    if not folder.exists():
        return ()
    if is_link(folder) or not folder.is_dir():
        raise ConflictError(f"A regular folder is required: {folder}")
    groups: dict[str, dict[str, list[Path]]] = {}
    for path in folder.iterdir():
        reason = ignored_file_reason(path)
        if reason:
            if ignored is not None and path.is_file():
                ignored[reason] = ignored.get(reason, 0) + 1
            continue
        extension = path.suffix.casefold()
        if extension not in RAW_EXTENSIONS | PREVIEW_EXTENSIONS:
            continue
        if is_link(path):
            raise ConflictError(f"Linked photos cannot be processed: {path.name}")
        if not path.is_file():
            continue
        group = groups.setdefault(path.stem.casefold(), {"jpeg": [], "raw": []})
        group["raw" if extension in RAW_EXTENSIONS else "jpeg"].append(path)
    photos = []
    for key, group in groups.items():
        if not group["jpeg"]:
            continue
        if len(group["jpeg"]) != 1 or len(group["raw"]) > 1:
            raise ConflictError(f"Multiple files have the same filename stem: {key}")
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
    with file_guard(source):
        _native_move_no_replace(source, target)


def _native_move_no_replace(source: Path, target: Path) -> None:
    if os.path.lexists(target):
        raise FileExistsError(f"Destination already exists: {target}")
    if sys.platform != "win32":
        raise AyiklaError("Ayikla's safe move engine requires Windows.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move = kernel32.MoveFileExW
    move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move.restype = ctypes.c_int
    # WRITE_THROUGH, without COPY_ALLOWED or REPLACE_EXISTING. No cross-volume move.
    if not move(str(source), str(target), 0x8):
        raise ctypes.WinError(ctypes.get_last_error())


class ShootSession:
    """One locked shoot. Close explicitly, or use as a context manager."""

    def __init__(self, root: str | Path, *, write_xmp: bool = False,
                 export_picks: bool = False, palette_cache: dict | None = None):
        self.write_xmp = write_xmp
        self.export_picks = export_picks
        self.palette_cache = palette_cache if palette_cache is not None else {}
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise AyiklaError("Choose a shoot folder.")
        self._lock = None
        self._log = None
        self.transactions: dict[str, dict] = {}
        self.receipts: dict[str, dict[int, dict]] = {}
        self.applied: dict[str, set[int]] = {}
        self.committed: set[str] = set()
        self.stack: list[str] = []
        self.edits: dict[str, str] = {}
        self.view: dict[str, str | None] = {"mode": "cull", "key": None}
        self.resume: dict = {}
        self.pending_id: str | None = None
        self.recovery_count = 0
        self.faulted = False
        self._photos: dict[str, Photo] | None = None
        self._order: tuple[str, ...] = ()
        self._snapshot: Snapshot | None = None
        self.ignored_files: dict[str, int] = {}
        try:
            for name in (KEPT, EDIT, REJECTED, ARCHIVE, LOG, ".ayikla.lock"):
                self._path(name)
            self._acquire_lock()
            self._log = (self.root / LOG).open("a+b", buffering=0)
            self._load_log()
            if self.pending_id:
                self.recover_pending()
            self.rescan()  # One filesystem scan on open, after journal recovery.
            if (self.root / "ayikla_import.jsonl").exists():
                from .importer import ImportJournal, _recover_stages
                _recover_stages(ImportJournal(self))
            self.resume_position = self.resolve_resume()
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
            raise ConflictError(f"Invalid path in journal: {relative}")
        result = self.root.joinpath(*rel.parts)
        if result == self.root or not result.resolve().is_relative_to(self.root):
            raise ConflictError(f"Path outside the shoot folder: {relative}")
        for part in (result, *result.parents):
            if part == self.root:
                break
            if is_link(part):
                raise ConflictError(f"File/folder links cannot be processed: {relative}")
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
            raise AyiklaError("This version requires Windows.")
        import msvcrt
        self._lock = (self.root / ".ayikla.lock").open("a+b")
        if self._lock.seek(0, os.SEEK_END) == 0:
            self._lock.write(b"\0")
            self._lock.flush()
        self._lock.seek(0)
        try:
            msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ConflictError("This shoot is open in another Ayikla window.") from error

    def _append(self, record: dict) -> None:
        assert self._log is not None
        payload = {"v": VERSION, "time": datetime.now(timezone.utc).isoformat(), **record}
        try:
            self._log.seek(0, os.SEEK_END)
            data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            if self._log.write(data) != len(data):
                raise OSError("Journal was not fully written to disk.")
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
                        raise RecoveryError(f"Journal line cannot be read ({number}). Files were not changed.")
                    self._append({"type": "repair", "line": number, "fragment_hex": line.hex()})
                continue
            try:
                self._replay(record)
            except (KeyError, TypeError, ValueError, IndexError) as error:
                raise RecoveryError(f"Invalid journal structure ({number}).") from error

    def _replay(self, record: dict) -> None:
        if not isinstance(record, dict) or record.get("v") != VERSION:
            raise RecoveryError("Unsupported journal version.")
        kind = record["type"]
        if kind == "begin":
            if self.pending_id or record["id"] in self.transactions:
                raise RecoveryError("Journal contains conflicting operations.")
            if record["action"] not in {"keep", "reject", "burst", "edit_mark", "edit_unmark", "undo", "picks_refresh", "import"}:
                raise RecoveryError("Journal contains an unknown decision.")
            for operation in record["ops"]:
                if operation["kind"] not in {"move", "copy", "write", "imported"}:
                    raise RecoveryError("Journal contains an unknown file operation.")
                if operation["kind"] not in {"write", "imported"}:
                    self._path(operation["src"])
                elif operation["kind"] == "write":
                    base64.b64decode(operation["content"], validate=True)
                self._path(operation["dst"])
                if operation["kind"] in {"copy", "write"}:
                    self._path(operation["stage"])
            self.transactions[record["id"]] = record
            self.receipts[record["id"]] = {}
            self.applied[record["id"]] = set()
            self.pending_id = record["id"]
        elif kind == "ready":
            if record["id"] != self.pending_id:
                raise RecoveryError("Journal contains an unmatched copy receipt.")
            self.receipts[record["id"]][record["index"]] = record["fingerprint"]
        elif kind == "applied":
            if record["id"] != self.pending_id or not 0 <= record["index"] < len(self.transactions[record["id"]]["ops"]):
                raise RecoveryError("Journal contains an unmatched operation checkpoint.")
            self.applied[record["id"]].add(record["index"])
        elif kind == "commit":
            if record["id"] != self.pending_id:
                raise RecoveryError("Journal contains an unmatched commit.")
            self._apply_commit(record["id"])
        elif kind == "view":
            self.view = self._validate_view(record["view"])
            if "resume" in record:
                resume = record["resume"]
                self._validate_view(resume)
                if (resume.get("filename") is not None and
                        (not isinstance(resume["filename"], str) or Path(resume["filename"]).name != resume["filename"])):
                    raise RecoveryError("Invalid resume filename.")
                if resume.get("capture_time") is not None:
                    datetime.fromisoformat(resume["capture_time"])
                self.resume = dict(resume)
        elif kind != "repair":
            raise RecoveryError("Journal contains an unknown record.")

    @staticmethod
    def _validate_view(view: dict) -> dict:
        if view.get("mode") not in {"cull", "edit"}:
            raise RecoveryError("Invalid round information in journal.")
        if view.get("key") is not None and not isinstance(view["key"], str):
            raise RecoveryError("Invalid photo information in journal.")
        return dict(view)

    def _apply_commit(self, transaction_id: str) -> None:
        tx = self.transactions[transaction_id]
        action, key = tx["action"], tx["key"]
        if action == "undo":
            if not self.stack or self.stack[-1] != tx["undo_of"]:
                raise RecoveryError("Invalid undo order.")
            target = self.transactions[self.stack.pop()]
            if target["action"] == "edit_mark":
                self.edits.pop(key, None)
            elif target["action"] == "edit_unmark":
                self.edits[key] = target["mark_id"]
        elif action != "picks_refresh":
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
            if effective == "import":
                self.rescan()
            if effective == "burst":
                group = self.transactions[tx["undo_of"]] if action == "undo" else tx
                for member in group["members"]:
                    state = member["before"] if action == "undo" else member["after"]
                    folder = self.root / {"pending": "", "kept": KEPT, "rejected": REJECTED}[state]
                    old = self._photos[member["key"]]
                    self._photos[old.key] = Photo(old.key, folder / old.jpeg.name,
                                                 folder / old.raw.name if old.raw else None, state)
                self._snapshot = None
            if effective in {"keep", "reject"}:
                state = "pending" if action == "undo" else ("kept" if action == "keep" else "rejected")
                paths = [self._path(op["dst"]) for op in tx["ops"]]
                jpeg = next(path for path in paths if path.suffix.casefold() in PREVIEW_EXTENSIONS)
                raw = next((path for path in paths if path.suffix.casefold() in RAW_EXTENSIONS), None)
                self._photos[key] = Photo(key, jpeg, raw, state)
                self._snapshot = None

    def rescan(self) -> Snapshot:
        """Explicit refresh on open, Retry or conflict; publish only a valid scan."""
        ignored: dict[str, int] = {}
        result = Snapshot(pair_photos(self.root, ignored=ignored),
                          pair_photos(self.root / KEPT, "kept", ignored=ignored),
                          pair_photos(self.root / REJECTED, "rejected", ignored=ignored))
        seen: set[str] = set()
        for photo in (*result.pending, *result.kept, *result.rejected):
            if photo.key in seen:
                raise ConflictError(f"The same photo exists in multiple folders: {photo.jpeg.name}")
            seen.add(photo.key)
        photos = (*result.pending, *result.kept, *result.rejected)
        self._photos = {photo.key: photo for photo in photos}
        self._order = tuple(photo.key for photo in sorted(photos, key=lambda item: natural_key(item.jpeg.name)))
        self._snapshot = result
        self.ignored_files = ignored
        return result

    @property
    def ignored_notice(self) -> str:
        parts = []
        if count := self.ignored_files.get("appledouble", 0):
            parts.append(f"{count} macOS helper files (._) ignored")
        if count := sum(value for reason, value in self.ignored_files.items() if reason != "appledouble"):
            parts.append(f"{count} hidden/system or helper files ignored")
        return " · ".join(parts)

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
        resume = dict(self.resume)
        photo = self._photos.get(key) if key else None
        if photo and (resume.get("key") != key or resume.get("mode") != mode or
                      resume.get("filename") != photo.jpeg.name):
            from .metadata import read_metadata
            taken = read_metadata(photo.jpeg).taken
            resume = {**view, "filename": photo.jpeg.name, "capture_time": taken.isoformat() if taken else None}
        elif resume.get("mode") != mode:
            resume = {**view, "filename": None, "capture_time": None}
        if self.view != view or self.resume != resume:
            self._append({"type": "view", "view": view, "resume": resume})
            self.view = view
            self.resume = resume

    def resolve_resume(self) -> tuple[str, str | None, bool]:
        """Resolve a portable bookmark without guessing a renamed file's identity."""
        mode = self.view["mode"]
        key = self.view["key"] or self.resume.get("key")
        candidates = self.snapshot().pending if mode == "cull" else self.snapshot().kept
        if not self.resume and not key:
            return mode, None, False
        filename = self.resume.get("filename") if key == self.resume.get("key") else None
        current = next((p for p in candidates if p.key == key and
                        (not filename or p.jpeg.name.casefold() == filename.casefold())), None)
        if current:
            return mode, current.key, True
        undecided = list(candidates if mode == "cull" else (p for p in candidates if p.key not in self.edits))
        if not undecided and mode == "edit" and self.snapshot().pending:
            mode, undecided = "cull", list(self.snapshot().pending)
        if not undecided:
            return mode, candidates[0].key if candidates else None, bool(candidates)
        timestamp = self.resume.get("capture_time")
        if timestamp:
            from .metadata import read_metadata
            reference = datetime.fromisoformat(timestamp)
            dated = [(p, read_metadata(p.jpeg).taken) for p in undecided]
            dated = [(p, taken) for p, taken in dated if taken is not None]
            if dated:
                closest = min(dated, key=lambda item: (abs((item[1] - reference).total_seconds()),
                                                       natural_key(item[0].jpeg.name)))
                return mode, closest[0].key, True
        return mode, undecided[0].key, True

    def _ensure_ready(self) -> None:
        if self._log is None:
            raise AyiklaError("The shoot is closed.")
        if self.faulted:
            raise RecoveryError("Journal could not be written to disk. Resolve the disk problem and reopen the app.")
        if self.pending_id:
            raise RecoveryError("An interrupted operation is pending. Press Retry first.")

    def _move_op(self, source: Path, target: Path, expected: dict | None = None) -> dict:
        self._path(self._relative(source))
        self._path(self._relative(target))
        if expected is not None and not same_file(source, expected):
            raise ConflictError(f"File was changed externally or is missing: {source.name}")
        return {"kind": "move", "src": self._relative(source),
                "dst": self._relative(target), "fingerprint": fingerprint(source)}

    def _preflight(self, operations: list[dict]) -> None:
        # Model earlier operations so archive-then-write and undo can share a path.
        virtual: dict[str, dict | None] = {}
        for op in operations:
            target = self._path(op["dst"])
            if op["kind"] == "imported":
                if not same_file(target, op["fingerprint"]):
                    raise ConflictError(f"Imported file changed: {target.name}")
                continue
            if op["kind"] != "write":
                source = self._path(op["src"])
                src_key = op["src"].casefold()
                if src_key in virtual:
                    matches = virtual[src_key] == op["fingerprint"]
                else:
                    matches = same_file(source, op["fingerprint"])
                if not matches:
                    raise ConflictError(f"Source file was changed or is missing: {source.name}")
                if source.exists() and ignored_file_reason(source):
                    raise ConflictError(f"Hidden/system or helper files cannot be processed: {source.name}. "
                                        "Press Retry to rescan the folder.")
                if op["kind"] == "move":
                    virtual[src_key] = None
            dst_key = op["dst"].casefold()
            occupied = virtual[dst_key] is not None if dst_key in virtual else self._existing(target) is not None
            if occupied:
                raise ConflictError(f"Destination already exists; nothing overwritten: {op['dst']}")
            virtual[dst_key] = op.get("fingerprint", {})
            for parent in target.parents:
                if parent == self.root:
                    break
                if parent.exists() and not parent.is_dir():
                    raise ConflictError(f"The destination folder path is a file: {parent.name}")

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
            if ignored_file_reason(source):
                raise ConflictError(f"Hidden/system or helper files cannot be moved: {source.name}")
            if existing is not None:
                raise ConflictError(f"Destination already exists: {operation['dst']}")
            if not same_file(source, operation["fingerprint"]):
                raise ConflictError(f"File was changed: {operation['src']}")
            target.parent.mkdir(parents=True, exist_ok=True)
            move_no_replace(source, target)
        elif existing is None or not same_file(target, operation["fingerprint"]):
            raise RecoveryError(f"Moved file could not be verified: {operation['dst']}")

    def _finish_copy(self, transaction_id: str, index: int, operation: dict) -> None:
        source, target = self._path(operation["src"]), self._path(operation["dst"])
        stage = self._path(operation["stage"])
        receipt = self.receipts[transaction_id].get(index)
        if receipt is None:
            if ignored_file_reason(source):
                raise ConflictError(f"Hidden/system or helper files cannot be copied: {source.name}")
            if self._existing(target) is not None:
                raise ConflictError(f"Copy destination already exists: {operation['dst']}")
            if not same_file(source, operation["fingerprint"]):
                raise ConflictError(f"Source to copy was changed: {operation['src']}")
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
                raise ConflictError(f"Source changed while copying: {source.name}")
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
            if index in self.applied[transaction_id]:
                continue
            if operation["kind"] == "move":
                self._finish_move(operation)
            elif operation["kind"] == "imported":
                from .importer import sha256_file
                target = self._path(operation["dst"])
                if not same_file(target, operation["fingerprint"]) or sha256_file(target) != operation["sha256"]:
                    raise RecoveryError(f"Imported file could not be verified: {target.name}")
            elif operation["kind"] == "write":
                self._finish_write(transaction_id, index, operation)
            else:
                self._finish_copy(transaction_id, index, operation)
            self._append({"type": "applied", "id": transaction_id, "index": index})
            self.applied[transaction_id].add(index)
        outputs = {}
        for index, operation in enumerate(self.transactions[transaction_id]["ops"]):
            if operation["kind"] == "move":
                outputs.pop(operation["src"].casefold(), None)
            expected = (operation["fingerprint"] if operation["kind"] in {"move", "imported"}
                        else self.receipts[transaction_id][index])
            outputs[operation["dst"].casefold()] = (operation["dst"], expected)
        for relative, expected in outputs.values():
            if not same_file(self._path(relative), expected):
                raise RecoveryError(f"Completed operation output changed externally: {relative}")
        self._append({"type": "commit", "id": transaction_id})
        self._apply_commit(transaction_id)

    def _finish_write(self, transaction_id: str, index: int, operation: dict) -> None:
        stage = self._path(operation["stage"])
        receipt = self.receipts[transaction_id].get(index)
        if receipt is None:
            target = self._path(operation["dst"])
            if self._existing(target) is not None:
                raise ConflictError(f"Sidecar destination already exists: {operation['dst']}")
            content = base64.b64decode(operation["content"], validate=True)
            if self._existing(stage) is not None:
                saved = self._path(f"{ARCHIVE}/yarim/{uuid.uuid4().hex}/{stage.name}")
                saved.parent.mkdir(parents=True, exist_ok=True)
                move_no_replace(stage, saved)
            stage.parent.mkdir(parents=True, exist_ok=True)
            with stage.open("xb") as stream:
                if stream.write(content) != len(content):
                    raise OSError("Sidecar was not fully written.")
                stream.flush()
                os.fsync(stream.fileno())
            receipt = fingerprint(stage)
            self._append({"type": "ready", "id": transaction_id, "index": index, "fingerprint": receipt})
            self.receipts[transaction_id][index] = receipt
        self._finish_move({"src": operation["stage"], "dst": operation["dst"], "fingerprint": receipt})

    def _write_op(self, target: Path, content: bytes, transaction_id: str) -> dict:
        relative = self._relative(target)
        token = hashlib.sha256(relative.encode()).hexdigest()[:16]
        return {"kind": "write", "dst": relative, "content": base64.b64encode(content).decode("ascii"),
                "stage": f"{ARCHIVE}/islem/{transaction_id}/{token}.part"}

    def register_import(self, import_id: str, files: list[dict]) -> None:
        if not files or any(tx.get("import_id") == import_id for tx in self.transactions.values()):
            return
        operations = [{"kind": "imported", "dst": item["dst"], "fingerprint": item["fingerprint"],
                       "sha256": item["sha256"]} for item in files]
        self._transaction("import", "", operations, dict(self.view), import_id=import_id)

    def _xmp_ops(self, photo: Photo, target: Path, rating: int, transaction_id: str, *, copy=False) -> list[dict]:
        if not self.write_xmp:
            return []
        from .xmp import merge
        source = (photo.raw or photo.jpeg).with_suffix(".xmp")
        destination = target / source.name
        existing_source = self._existing(source)
        existing_dest = self._existing(destination)
        original_path = existing_dest if copy else existing_source
        if not copy and existing_dest and destination != source:
            raise ConflictError(f"XMP destination already exists: {destination.name}")
        read_path = original_path or (existing_source if copy else None)
        if read_path:
            self._path(self._relative(read_path))
            expected = fingerprint(read_path)
            content = read_path.read_bytes()
            if not same_file(read_path, expected):
                raise ConflictError("XMP changed while reading it.")
        else:
            content = None
        try:
            merged = merge(content, rating)
        except (ValueError, UnicodeError) as error:
            raise ConflictError(f"Cannot merge {source.name}: {error}") from error
        operations = []
        if original_path:
            saved = self._path(f"{ARCHIVE}/xmp/{transaction_id}/{hashlib.sha256(self._relative(original_path).encode()).hexdigest()[:16]}/{original_path.name}")
            operations.append(self._move_op(original_path, saved, expected))
        operations.append(self._write_op(destination, merged, transaction_id))
        return operations

    def _picks_ops(self, keys: set[str], transaction_id: str) -> list[dict]:
        if not self.export_picks:
            return []
        from .picks import serialize
        content = serialize((photo for photo in self.all_photos() if photo.key in keys), self.palette_cache)
        target = self._path(f"{EDIT}/ayikla_picks.json")
        existing = self._existing(target)
        operations = []
        if existing:
            expected = fingerprint(existing)
            previous = existing.read_bytes()
            if not same_file(existing, expected):
                raise ConflictError("Picks JSON changed while reading it.")
            if previous == content:
                return []
            saved = self._path(f"{ARCHIVE}/picks/{transaction_id}/ayikla_picks.json")
            operations.append(self._move_op(existing, saved, expected))
        operations.append(self._write_op(target, content, transaction_id))
        for operation in operations:
            operation["role"] = "picks"
        return operations

    def refresh_picks(self) -> str:
        self._ensure_ready()
        transaction_id = uuid.uuid4().hex
        operations = self._picks_ops(set(self.edits), transaction_id)
        if operations:
            self._transaction("picks_refresh", "", operations, dict(self.view), transaction_id)
        return "picks_refreshed"

    def recover_pending(self) -> None:
        if self.faulted:
            raise RecoveryError("Reopen the app after a journal error.")
        if self.pending_id:
            self._finish_pending()
            self.recovery_count += 1
        if self._photos is not None:
            self.rescan()

    @rescan_on_conflict
    def decide_burst(self, photos: tuple[Photo, ...], selected: str) -> None:
        """One durable decision, including the previous state of every member."""
        self._ensure_ready()
        if len(photos) < 2 or len({p.key for p in photos}) != len(photos) or selected not in {p.key for p in photos}:
            raise ConflictError("Choose one frame from this burst.")
        operations, members = [], []
        transaction_id = uuid.uuid4().hex
        for photo in photos:
            if self._photos.get(photo.key) != photo or photo.key in self.edits:
                raise ConflictError("Burst changed or contains edit picks. Refresh or remove edit picks first.")
            self._check_raw_partner(photo)
            state = "kept" if photo.key == selected else "rejected"
            members.append({"key": photo.key, "before": photo.state, "after": state})
            target = self.root / (KEPT if state == "kept" else REJECTED)
            if photo.state != state:
                operations.extend(self._move_op(path, target / path.name) for path in photo.files)
            operations.extend(self._xmp_ops(photo, target, 1 if state == "kept" else -1, transaction_id))
        self._transaction("burst", selected, operations, {"mode": "edit", "key": selected},
                          transaction_id, members=members)

    def _check_raw_partner(self, photo: Photo) -> None:
        for extension in RAW_EXTENSIONS:
            candidate = photo.jpeg.with_suffix(extension.upper())
            if photo.raw and candidate.name.casefold() == photo.raw.name.casefold():
                continue
            if candidate.is_file() and not ignored_file_reason(candidate):
                raise ConflictError(f"A new {extension[1:].upper()} RAW partner was found. "
                                    "Press Retry to rescan, then make the decision again.")

    @rescan_on_conflict
    def decide(self, photo: Photo, keep: bool, next_key: str | None = None) -> None:
        self._ensure_ready()
        current = self._photos.get(photo.key)
        if current is None or current != photo or current.state != "pending":
            raise ConflictError("This photo is no longer in the shoot root. Reopen the folder.")
        self._check_raw_partner(photo)
        target = self.root / (KEPT if keep else REJECTED)
        transaction_id = uuid.uuid4().hex
        operations = [self._move_op(path, target / path.name) for path in photo.files]
        operations.extend(self._xmp_ops(photo, target, 1 if keep else -1, transaction_id))
        self._transaction("keep" if keep else "reject", photo.key, operations,
                          {"mode": "cull", "key": next_key}, transaction_id)

    @rescan_on_conflict
    def toggle_edit(self, photo: Photo) -> bool:
        self._ensure_ready()
        current = self._photos.get(photo.key)
        if current is None or current != photo or current.state != "kept":
            raise ConflictError("Only photos in 01_secilen can be picked for editing.")
        transaction_id = uuid.uuid4().hex
        view = {"mode": "edit", "key": photo.key}
        if photo.key in self.edits:
            mark_id = self.edits[photo.key]
            mark = self.transactions[mark_id]
            operations = self._inverse_ops(mark_id, transaction_id, include_picks=False)
            operations.extend(self._picks_ops(set(self.edits) - {photo.key}, transaction_id))
            self._transaction("edit_unmark", photo.key, operations, view,
                              transaction_id, mark_id=mark_id)
            return False
        operations = [{"kind": "copy", "src": self._relative(path),
                       "dst": f"{EDIT}/{path.name}",
                       "stage": f"{ARCHIVE}/islem/{transaction_id}/{path.name}.part",
                       "fingerprint": fingerprint(path)} for path in photo.files]
        operations.extend(self._xmp_ops(photo, self.root / EDIT, 3, transaction_id, copy=True))
        operations.extend(self._picks_ops(set(self.edits) | {photo.key}, transaction_id))
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
        operations = self._inverse_ops(target_id, transaction_id)
        self._transaction("undo", target["key"], operations, target["view_before"],
                          transaction_id, undo_of=target_id)
        return True

    def _inverse_ops(self, target_id: str, transaction_id: str, *, include_picks=True) -> list[dict]:
        target = self.transactions[target_id]
        operations = []
        for index, op in reversed(list(enumerate(target["ops"]))):
            if not include_picks and op.get("role") == "picks":
                continue
            source = self._path(op["dst"])
            if op["kind"] == "move":
                destination, expected = self._path(op["src"]), op["fingerprint"]
            else:
                token = hashlib.sha256(op["dst"].encode()).hexdigest()[:16]
                destination = self._path(f"{ARCHIVE}/geri_alinan/{transaction_id}/{token}/{source.name}")
                expected = op["fingerprint"] if op["kind"] == "imported" else self.receipts[target_id][index]
            operations.append(self._move_op(source, destination, expected))
        return operations
