"""Verified card copies. Sources are read only; published photos are never deleted."""

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Event

from .core import (ARCHIVE, PREVIEW_EXTENSIONS, RAW_EXTENSIONS, ConflictError,
                   RecoveryError, ShootSession, fingerprint, ignored_file_reason,
                   is_link, move_no_replace, natural_key, same_file)

IMPORT_LOG = "ayikla_import.jsonl"
CHUNK = 1024 * 1024


class ImportCancelled(Exception):
    pass


@dataclass(frozen=True)
class ImportResult:
    folder: Path
    copied: int
    skipped: int
    cancelled: bool


def sha256_file(path: Path, cancel: Event | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            if cancel and cancel.is_set():
                raise ImportCancelled()
            chunk = stream.read(CHUNK)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


class ImportJournal:
    def __init__(self, session):
        self.session = session
        self.path = session._path(IMPORT_LOG)
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            data = b""
        self.records = []
        self.repairs = []
        lines = data.splitlines()
        for index, line in enumerate(lines):
            if not line:
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict) or record.get("v") != 1:
                    raise ValueError()
                self.records.append(record)
            except (ValueError, UnicodeError):
                repaired = any(b'"type": "repair"' in later and
                               f'"fragment_hex": "{line.hex()}"'.encode() in later for later in lines[index + 1:])
                if repaired:
                    continue
                if index != len(lines) - 1 or data.endswith(b"\n"):
                    raise RecoveryError("Import journal is invalid; preserve it unchanged.")
                self.repairs.append({"v": 1, "type": "repair", "fragment_hex": line.hex()})
        self.torn = data and not data.endswith(b"\n")

    def append(self, record):
        record = {"v": 1, **record}
        with self.path.open("ab", buffering=0) as stream:
            if self.torn:
                stream.write(b"\n")
                self.torn = False
            for repair in self.repairs:
                stream.write((json.dumps(repair) + "\n").encode())
            self.repairs.clear()
            payload = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
            if stream.write(payload) != len(payload):
                raise OSError("Import journal was not fully written.")
            os.fsync(stream.fileno())
        self.records.append(record)


def adopt_imports(session):
    """Recover published copies into the shoot's durable undo stack."""
    journal = ImportJournal(session)
    batches = {}
    for record in journal.records:
        if record.get("type") == "published":
            batches.setdefault(record["batch"], []).append(record)
    for batch, files in batches.items():
        session.register_import(batch, files)


def _regular_tree(path):
    absolute = Path(os.path.abspath(path))
    if any(is_link(part) for part in (absolute, *absolute.parents)):
        raise ConflictError("Import source and destination cannot contain folder links.")
    return absolute.resolve(strict=True)


def import_folder(source, destination_root, name, *, cancel=None, progress=None,
                  today=None, active_session=None):
    cancel = cancel if cancel is not None else Event()
    progress = progress or (lambda done, total, name: None)
    name = name.strip()
    if (not name or len(name) > 80 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.endswith((".", " ")) or name in {".", ".."}):
        raise ConflictError("Enter a shoot name without path separators or Windows filename symbols.")
    source, root = _regular_tree(source), _regular_tree(destination_root)
    if not source.is_dir() or not root.is_dir():
        raise ConflictError("Choose existing source and destination folders.")
    folder = root / f"{(today or date.today()).isoformat()}_{name}"
    if folder.is_relative_to(source) or source.is_relative_to(folder):
        raise ConflictError("The import destination must be outside the source/card.")
    if folder.exists() and is_link(folder):
        raise ConflictError("The import destination cannot be a folder link.")
    files = []
    for directory, children, filenames in os.walk(source, followlinks=False):
        children[:] = sorted(child for child in children
                             if not is_link(Path(directory) / child)
                             and not ignored_file_reason(Path(directory) / child))
        for filename in sorted(filenames, key=natural_key):
            path = Path(directory) / filename
            if path.suffix.casefold() not in RAW_EXTENSIONS | PREVIEW_EXTENSIONS:
                continue
            if is_link(path):
                raise ConflictError(f"Linked card files cannot be imported: {path.name}")
            if not ignored_file_reason(path):
                files.append(path)
        if cancel.is_set():
            return ImportResult(folder, 0, 0, True)
    if not files:
        raise ConflictError("No supported JPEG, TIFF or RAW files were found in the source.")
    groups = {}
    for path in files:
        group = groups.setdefault(path.stem.casefold(), {"preview": set(), "raw": set()})
        group["raw" if path.suffix.casefold() in RAW_EXTENSIONS else "preview"].add(path.name.casefold())
    if any(len(group["preview"]) > 1 or len(group["raw"]) > 1 for group in groups.values()):
        raise ConflictError("Card files have ambiguous JPEG/TIFF or RAW partners with the same stem.")
    folder.mkdir(exist_ok=True)
    owned = active_session is None or active_session.root != folder
    session = ShootSession(folder) if owned else active_session
    copied = skipped = 0
    batch = uuid.uuid4().hex
    journal = ImportJournal(session)
    try:
        _recover_stages(journal)
        catalog = {path.name.casefold(): path for photo in session.all_photos() for path in photo.files}
        photos_by_key = {photo.key: photo for photo in session.all_photos()}
        journal.append({"type": "batch", "batch": batch, "source": str(source)})
        for index, path in enumerate(files):
            if cancel.is_set():
                break
            progress(index, len(files), path.name)
            partner = photos_by_key.get(path.stem.casefold())
            if partner:
                raw = path.suffix.casefold() in RAW_EXTENSIONS
                if ((not raw and partner.jpeg.name.casefold() != path.name.casefold()) or
                        (raw and partner.raw and partner.raw.name.casefold() != path.name.casefold())):
                    raise ConflictError(f"An ambiguous photo partner already exists: {path.name}")
                destination = session._path(session._relative(partner.jpeg.parent / path.name))
            else:
                destination = session._path(path.name)
            existing = session._existing(destination) or catalog.get(path.name.casefold())
            before = fingerprint(path)
            if existing:
                expected = fingerprint(existing)
                if (before["size"] != expected["size"] or sha256_file(path, cancel) != sha256_file(existing, cancel)
                        or not same_file(path, before) or not same_file(existing, expected)):
                    raise ConflictError(f"A different file already exists; nothing overwritten: {path.name}")
                journal.append({"type": "skip", "batch": batch, "dst": path.name})
                skipped += 1
            else:
                _copy_one(session, journal, batch, path, before, cancel, destination)
                copied += 1
            progress(index + 1, len(files), path.name)
        journal.append({"type": "end", "batch": batch, "cancelled": cancel.is_set()})
        return ImportResult(folder, copied, skipped, cancel.is_set())
    except ImportCancelled:
        journal.append({"type": "end", "batch": batch, "cancelled": True})
        return ImportResult(folder, copied, skipped, True)
    finally:
        try:
            adopt_imports(session)
            session.rescan()
        finally:
            if owned:
                session.close()


def _discard_stage(journal, begin):
    stage = journal.session._path(begin["stage"])
    if not stage.exists():
        return
    expected = fingerprint(stage)
    # Only our exclusive .part staging file may be removed; never a photo path.
    if not begin["stage"].startswith(f"{ARCHIVE}/import/") or stage.suffix != ".part":
        raise RecoveryError("Invalid import staging path.")
    journal.append({"type": "discard", "id": begin["id"], "stage": begin["stage"], "fingerprint": expected})
    if not same_file(stage, expected):
        raise ConflictError("Import staging file changed externally.")
    stage.unlink()
    journal.append({"type": "discarded", "id": begin["id"]})


def _recover_stages(journal):
    begins, verified, finished = {}, {}, set()
    for record in journal.records:
        kind = record.get("type")
        if kind == "begin":
            begins[record["id"]] = record
        elif kind == "verified":
            verified[record["id"]] = record
        elif kind in {"published", "discarded"}:
            finished.add(record["id"])
    for identity, begin in begins.items():
        if identity in finished:
            continue
        stage, target = journal.session._path(begin["stage"]), journal.session._path(begin["dst"])
        ready = verified.get(identity)
        if ready and target.exists() and not stage.exists():
            if not same_file(target, ready["fingerprint"]) or sha256_file(target) != ready["sha256"]:
                raise RecoveryError("Interrupted import destination changed externally.")
            journal.append({**ready, "type": "published", "batch": begin["batch"], "dst": begin["dst"]})
        else:
            # A new explicit import can recopy it; no unverified file is published.
            _discard_stage(journal, begin)
    adopt_imports(journal.session)


def _copy_one(session, journal, batch, source, expected, cancel, destination):
    identity = uuid.uuid4().hex
    relative = f"{ARCHIVE}/import/{identity}/copy.part"
    stage = session._path(relative)
    target_relative = session._relative(destination)
    begin = {"type": "begin", "id": identity, "batch": batch, "src": str(source),
             "dst": target_relative, "stage": relative, "fingerprint": expected}
    journal.append(begin)
    stage.parent.mkdir(parents=True, exist_ok=False)
    published = False
    try:
        digest, size = hashlib.sha256(), 0
        with source.open("rb") as input_file, stage.open("xb") as output:
            while True:
                if cancel.is_set():
                    raise ImportCancelled()
                chunk = input_file.read(CHUNK)
                if not chunk:
                    break
                if output.write(chunk) != len(chunk):
                    raise OSError("Import copy was not fully written.")
                digest.update(chunk)
                size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        if (size != expected["size"] or not same_file(source, expected)
                or stage.stat().st_size != size or sha256_file(stage, cancel) != digest.hexdigest()):
            raise RecoveryError(f"Import size/SHA-256 verification failed: {source.name}")
        if cancel.is_set():
            raise ImportCancelled()
        ready = {"type": "verified", "id": identity, "sha256": digest.hexdigest(), "fingerprint": fingerprint(stage)}
        journal.append(ready)
        move_no_replace(stage, destination)
        published = True
        journal.append({**ready, "type": "published", "batch": batch, "dst": target_relative})
    finally:
        if not published:
            _discard_stage(journal, begin)
