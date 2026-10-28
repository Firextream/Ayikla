import json
from datetime import date
from pathlib import Path
from threading import Event

import pytest
from PIL import Image

from ayikla import importer
from ayikla.core import ShootSession, ConflictError, RecoveryError, ARCHIVE


@pytest.fixture
def card(tmp_path):
    source = tmp_path / "card" / "DCIM" / "100TEST"
    source.mkdir(parents=True)
    Image.new("RGB", (80, 60), "gray").save(source / "IMG_1.JPG")
    (source / "IMG_1.CR3").write_bytes(b"generated RAW" * 100)
    destination = tmp_path / "shoots"
    destination.mkdir()
    return source.parent.parent, destination


def original_bytes(source):
    return {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()}


def test_verified_recursive_import_skip_and_group_undo_after_restart(card):
    source, root = card
    before = original_bytes(source)
    result = importer.import_folder(source, root, "club", today=date(2026, 10, 29))
    assert result.folder.name == "2026-10-29_club" and result.copied == 2 and not result.cancelled
    assert not list(result.folder.rglob("*.part"))
    assert original_bytes(source) == before
    records = [json.loads(line) for line in (result.folder / importer.IMPORT_LOG).read_text("utf-8").splitlines()]
    assert len([r for r in records if r["type"] == "verified"]) == 2
    again = importer.import_folder(source, root, "club", today=date(2026, 10, 29))
    assert again.skipped == 2 and again.copied == 0
    with ShootSession(result.folder) as session:
        assert len(session.stack) == 1
        assert session.undo()
        assert not list(result.folder.glob("*.JPG")) and not list(result.folder.glob("*.CR3"))
        assert len(list((result.folder / ARCHIVE).rglob("*.JPG"))) == 1
    assert original_bytes(source) == before


def test_reimport_skips_identical_files_already_culled(card):
    source, root = card
    result = importer.import_folder(source, root, "same")
    with ShootSession(result.folder) as session:
        session.decide(session.snapshot().pending[0], True)
        second = importer.import_folder(source, root, "same", active_session=session)
        assert second.skipped == 2 and second.copied == 0
        assert len(session.snapshot().kept) == 1 and not session.snapshot().pending


def test_different_existing_content_is_never_overwritten(card):
    source, root = card
    result = importer.import_folder(source, root, "collision")
    target = result.folder / "IMG_1.JPG"
    target.write_bytes(b"external photo")
    with pytest.raises(ConflictError, match="nothing overwritten"):
        importer.import_folder(source, root, "collision")
    assert target.read_bytes() == b"external photo"


def test_cancel_during_copy_removes_only_partial_staging_file(card, monkeypatch):
    source, root = card
    cancel = Event()
    (source / "DCIM" / "100TEST" / "IMG_1.CR3").write_bytes(b"RAW" * 1000)
    monkeypatch.setattr(importer, "CHUNK", 7)
    original_hash = importer.hashlib.sha256
    class CancellingHash:
        def __init__(self):
            self.value = original_hash()
        def update(self, chunk):
            self.value.update(chunk)
            cancel.set()
        def hexdigest(self):
            return self.value.hexdigest()
    monkeypatch.setattr(importer.hashlib, "sha256", CancellingHash)
    result = importer.import_folder(source, root, "cancel", cancel=cancel)
    assert result.cancelled and result.copied == 0
    assert not list(result.folder.glob("*.CR3"))
    assert not list(result.folder.rglob("*.part"))


def test_cancel_between_files_keeps_verified_files_and_supports_undo(card):
    source, root = card
    cancel = Event()
    def progress(done, total, name):
        if done == 1:
            cancel.set()
    result = importer.import_folder(source, root, "partial", cancel=cancel, progress=progress)
    assert result.cancelled and result.copied == 1
    assert not list(result.folder.rglob("*.part"))
    # Natural order copies CR3 first, so an unmatched RAW is preserved too.
    with ShootSession(result.folder) as session:
        assert session.undo()
        assert not list(result.folder.glob("*.CR3"))


def test_failed_sha256_verification_never_publishes(card, monkeypatch):
    source, root = card
    original = importer.sha256_file
    monkeypatch.setattr(importer, "sha256_file", lambda path, cancel=None:
                        "0" * 64 if path.suffix == ".part" else original(path, cancel))
    with pytest.raises(RecoveryError, match="verification failed"):
        importer.import_folder(source, root, "bad")
    folder = next(root.iterdir())
    assert not list(folder.glob("*.CR3")) and not list(folder.rglob("*.part"))


def test_crash_after_publish_is_adopted_on_reopen(card, monkeypatch):
    source, root = card
    original = importer.ImportJournal.append
    def crash(journal, record):
        if record["type"] == "published":
            raise OSError("simulated crash after rename")
        original(journal, record)
    monkeypatch.setattr(importer.ImportJournal, "append", crash)
    with pytest.raises(OSError):
        importer.import_folder(source, root, "crash")
    monkeypatch.setattr(importer.ImportJournal, "append", original)
    with ShootSession(next(root.iterdir())) as session:
        assert len(session.stack) == 1 and session.undo()


@pytest.mark.parametrize("name", ["../outside", "bad/name", "bad:name", "", "a" * 81])
def test_invalid_names_and_source_overlap_are_rejected(card, name):
    source, root = card
    with pytest.raises(ConflictError):
        importer.import_folder(source, root, name)
    with pytest.raises(ConflictError, match="outside"):
        importer.import_folder(source, source, "nested")


def test_ambiguous_card_partners_are_rejected_before_copy(card):
    source, root = card
    (source / "DCIM" / "100TEST" / "IMG_1.jpeg").write_bytes(b"another preview")
    with pytest.raises(ConflictError, match="ambiguous"):
        importer.import_folder(source, root, "ambiguous")
    assert not list(root.iterdir())


def test_late_raw_partner_follows_previously_kept_jpeg(card):
    source, root = card
    raw = source / "DCIM" / "100TEST" / "IMG_1.CR3"
    raw.rename(raw.with_suffix(".txt"))
    result = importer.import_folder(source, root, "late-raw")
    with ShootSession(result.folder) as session:
        session.decide(session.snapshot().pending[0], True)
    raw.with_suffix(".txt").rename(raw)
    result = importer.import_folder(source, root, "late-raw")
    assert result.copied == 1 and result.skipped == 1
    with ShootSession(result.folder) as session:
        assert session.snapshot().kept[0].raw.parent.name == "01_secilen"
        assert session.undo()
        assert session.snapshot().kept[0].raw is None


def test_torn_import_journal_preserves_fragment_and_reopens(card):
    source, root = card
    result = importer.import_folder(source, root, "torn")
    journal = result.folder / importer.IMPORT_LOG
    with journal.open("ab") as stream:
        stream.write(b'{"v":1,"type":')
    before = journal.read_bytes()
    importer.import_folder(source, root, "torn")
    assert journal.read_bytes().startswith(before)
    with ShootSession(result.folder) as session:
        assert session.snapshot().total == 1
