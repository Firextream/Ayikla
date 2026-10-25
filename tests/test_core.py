import json
from pathlib import Path

import pytest

from ayikla import core
from ayikla.core import (
    ARCHIVE, EDIT, KEPT, LOG, REJECTED, AyiklaError, ConflictError,
    RecoveryError, ShootSession, pair_photos,
)


def file_bytes(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*") if p.suffix.casefold() in {".jpg", ".jpeg", ".cr3"}}


def records(folder: Path) -> list[dict]:
    return [json.loads(line) for line in (folder / LOG).read_text("utf-8").splitlines()]


def test_pairing_case_insensitive_natural_and_nonrecursive(shoot):
    for name in ("IMG_10.JPG", "img_10.cR3", "IMG_2.jpeg", "Img_2.CR3", "lone.CR3", "readme.txt"):
        (shoot / name).write_bytes(b"dummy")
    (shoot / "nested").mkdir()
    (shoot / "nested" / "hidden.JPG").write_bytes(b"dummy")
    photos = pair_photos(shoot)
    assert [p.key for p in photos] == ["img_2", "img_10"]
    assert photos[0].raw.name == "Img_2.CR3"
    assert photos[1].raw.name == "img_10.cR3"


def test_ambiguous_jpeg_stem_rejected(shoot):
    (shoot / "IMG.JPG").write_bytes(b"a")
    (shoot / "img.jpeg").write_bytes(b"b")
    with pytest.raises(ConflictError):
        pair_photos(shoot)


@pytest.mark.parametrize("keep,directory", [(True, KEPT), (False, REJECTED)])
def test_keep_reject_and_exact_path_undo(shoot, make_pair, keep, directory):
    (shoot / "iMg_1234.jPg").write_bytes(b"jpeg")
    (shoot / "IMG_1234.cR3").write_bytes(b"raw")
    before = file_bytes(shoot)
    with ShootSession(shoot) as session:
        photo = session.snapshot().pending[0]
        session.save_view("cull", photo.key)
        session.decide(photo, keep)
        assert not (shoot / photo.jpeg.name).exists()
        assert (shoot / directory / photo.jpeg.name).read_bytes() == b"jpeg"
        assert (shoot / directory / photo.raw.name).read_bytes() == b"raw"
        assert session.undo()
        assert file_bytes(shoot) == before
        assert session.view == {"mode": "cull", "key": photo.key}
        assert not session.undo()


def test_missing_raw_keeps_rejects_undo_and_edit(shoot, make_pair):
    make_pair(shoot, raw=False)
    with ShootSession(shoot) as session:
        photo = session.snapshot().pending[0]
        assert photo.raw is None
        session.decide(photo, False)
        assert len(session.snapshot().rejected) == 1
        session.undo()
        session.decide(session.snapshot().pending[0], True)
        kept = session.snapshot().kept[0]
        assert session.toggle_edit(kept)
        assert (shoot / EDIT / kept.jpeg.name).exists()
        assert list((shoot / EDIT).glob("*.CR3")) == []
        assert not session.toggle_edit(kept)
        assert not (shoot / EDIT / kept.jpeg.name).exists()
        assert any((shoot / ARCHIVE).rglob("*.JPG"))


def test_edit_toggle_is_copy_and_never_deletes(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        kept = session.snapshot().kept[0]
        original = {p.name: p.read_bytes() for p in kept.files}
        assert session.toggle_edit(kept)
        for path in kept.files:
            assert path.read_bytes() == original[path.name]
            assert (shoot / EDIT / path.name).read_bytes() == original[path.name]
        assert not session.toggle_edit(kept)
        assert not list((shoot / EDIT).iterdir())
        saved = [p for p in (shoot / ARCHIVE).rglob("*") if p.is_file()]
        assert sorted(p.read_bytes() for p in saved) == sorted(original.values())
        assert session.undo()  # Undo unmark restores the exact copies.
        assert kept.key in session.edits
        for path in kept.files:
            assert (shoot / EDIT / path.name).read_bytes() == original[path.name]
        assert session.undo()  # Undo mark archives copies instead of deleting them.
        assert kept.key not in session.edits
        assert not list((shoot / EDIT).iterdir())
        assert session.undo()  # Undo keep finally restores the originals.
        assert len(session.snapshot().pending) == 1


@pytest.mark.parametrize("directory", [KEPT, REJECTED])
def test_preflight_raw_collision_moves_neither_file(shoot, make_pair, directory):
    make_pair(shoot)
    (shoot / directory).mkdir()
    collision = shoot / directory / "img_1234.cr3"
    collision.write_bytes(b"preexisting raw")
    before = file_bytes(shoot)
    with ShootSession(shoot) as session:
        with pytest.raises(ConflictError):
            session.decide(session.snapshot().pending[0], directory == KEPT)
        assert file_bytes(shoot) == before
        assert not session.stack and session.pending_id is None


def test_edit_no_overwrite_even_if_jpeg_target_is_free(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        (shoot / EDIT).mkdir()
        (shoot / EDIT / "img_1234.cr3").write_bytes(b"external raw")
        before = file_bytes(shoot)
        with pytest.raises(ConflictError):
            session.toggle_edit(session.snapshot().kept[0])
        assert file_bytes(shoot) == before
        assert not session.edits


def test_undo_collision_preserves_both_locations(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        (shoot / "IMG_1234.CR3").write_bytes(b"new file")
        before = file_bytes(shoot)
        with pytest.raises(ConflictError):
            session.undo()
        assert file_bytes(shoot) == before
        assert len(session.stack) == 1


def test_native_move_also_refuses_overwrite(shoot):
    source, destination = shoot / "source.JPG", shoot / "target.JPG"
    source.write_bytes(b"source")
    destination.write_bytes(b"target")
    with pytest.raises(OSError):
        core.move_no_replace(source, destination)
    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"target"


def test_resume_view_undo_history_and_edit_selection(shoot, make_pair):
    for stem in ("IMG_1", "IMG_2", "IMG_3"):
        make_pair(shoot, stem)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True, "img_2")
        session.decide(session.snapshot().pending[0], False, "img_3")
        session.toggle_edit(session.snapshot().kept[0])
        session.save_view("cull", "img_3")
    with ShootSession(shoot) as resumed:
        assert resumed.view == {"mode": "cull", "key": "img_3"}
        assert len(resumed.stack) == 3
        assert set(resumed.edits) == {"img_1"}
        assert resumed.undo()
        assert not resumed.edits
    with ShootSession(shoot) as resumed:
        assert len(resumed.stack) == 2
        assert resumed.undo()
        assert {p.key for p in resumed.snapshot().pending} == {"img_2", "img_3"}
        assert resumed.undo()
        assert len(resumed.snapshot().pending) == 3


def test_one_writer_per_shoot(shoot):
    with ShootSession(shoot):
        with pytest.raises(ConflictError, match="başka"):
            ShootSession(shoot)
    with ShootSession(shoot):
        pass


def test_changed_edit_copy_not_archived_or_overwritten(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        photo = session.snapshot().kept[0]
        session.toggle_edit(photo)
        (shoot / EDIT / "IMG_1234.CR3").write_bytes(b"externally modified")
        before = file_bytes(shoot)
        with pytest.raises(ConflictError):
            session.toggle_edit(photo)
        assert file_bytes(shoot) == before
        assert photo.key in session.edits


def interrupt_once(monkeypatch, function_name, after):
    real = getattr(core, function_name)
    count = 0

    def interrupted(*args, **kwargs):
        nonlocal count
        count += 1
        if count == after:
            raise OSError("simulated disk interruption")
        return real(*args, **kwargs)

    monkeypatch.setattr(core, function_name, interrupted)
    return real


def test_crash_between_pair_moves_completes_on_restart(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    real = interrupt_once(monkeypatch, "move_no_replace", 2)
    with ShootSession(shoot) as session:
        with pytest.raises(OSError):
            session.decide(session.snapshot().pending[0], True)
        assert session.pending_id
        assert (shoot / KEPT / "IMG_1234.JPG").exists()
        assert (shoot / "IMG_1234.CR3").exists()
    monkeypatch.setattr(core, "move_no_replace", real)
    with ShootSession(shoot) as resumed:
        assert resumed.recovery_count == 1
        assert len(resumed.snapshot().kept) == 1
        assert resumed.undo()
        assert len(resumed.snapshot().pending) == 1


def test_crash_after_move_before_receiving_success(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    real = core.move_no_replace

    def move_then_crash(*args):
        real(*args)
        raise OSError("simulated process death after atomic move")

    monkeypatch.setattr(core, "move_no_replace", move_then_crash)
    with ShootSession(shoot) as session:
        with pytest.raises(OSError):
            session.decide(session.snapshot().pending[0], False)
    monkeypatch.setattr(core, "move_no_replace", real)
    with ShootSession(shoot) as resumed:
        assert len(resumed.snapshot().rejected) == 1
        assert resumed.undo()


def test_crash_during_copy_preserves_partial_and_retries(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        real = core.shutil.copyfileobj

        def partial_copy(source, destination, **_):
            destination.write(source.read(3))
            raise OSError("simulated process death during copy")

        monkeypatch.setattr(core.shutil, "copyfileobj", partial_copy)
        with pytest.raises(OSError):
            session.toggle_edit(session.snapshot().kept[0])
    monkeypatch.setattr(core.shutil, "copyfileobj", real)
    with ShootSession(shoot) as resumed:
        assert set(resumed.edits) == {"img_1234"}
        assert (shoot / EDIT / "IMG_1234.CR3").read_bytes() == (shoot / KEPT / "IMG_1234.CR3").read_bytes()
        assert any(p.read_bytes() == b"dum" for p in (shoot / ARCHIVE / "yarim").rglob("*.part"))
        assert resumed.undo()


@pytest.mark.parametrize("fail_at", [1, 2])
def test_crash_copy_ready_receipt_then_publish(shoot, make_pair, monkeypatch, fail_at):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        real = interrupt_once(monkeypatch, "move_no_replace", fail_at)
        with pytest.raises(OSError):
            session.toggle_edit(session.snapshot().kept[0])
    monkeypatch.setattr(core, "move_no_replace", real)
    with ShootSession(shoot) as resumed:
        assert set(resumed.edits) == {"img_1234"}
        assert len(list((shoot / EDIT).iterdir())) == 2
        assert resumed.undo()


def test_crash_before_commit_replays_completed_moves(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        real = session._append

        def fail_commit(record):
            if record["type"] == "commit":
                raise OSError("simulated process death before commit")
            real(record)

        monkeypatch.setattr(session, "_append", fail_commit)
        with pytest.raises(OSError):
            session.decide(session.snapshot().pending[0], True)
    with ShootSession(shoot) as resumed:
        assert len(resumed.snapshot().kept) == 1
        assert len(resumed.stack) == 1
        assert resumed.undo()


def test_crash_during_undo_and_unmark(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        session.toggle_edit(session.snapshot().kept[0])
        real = interrupt_once(monkeypatch, "move_no_replace", 2)
        with pytest.raises(OSError):
            session.toggle_edit(session.snapshot().kept[0])
    monkeypatch.setattr(core, "move_no_replace", real)
    with ShootSession(shoot) as resumed:
        assert not resumed.edits
        assert resumed.undo()  # Undo completed unmark.
        assert resumed.edits
        assert resumed.undo()  # Undo mark.
        real = interrupt_once(monkeypatch, "move_no_replace", 2)
        with pytest.raises(OSError):
            resumed.undo()  # Undo keep dies after first file.
    monkeypatch.setattr(core, "move_no_replace", real)
    with ShootSession(shoot) as resumed:
        assert len(resumed.snapshot().pending) == 1
        assert not resumed.stack


def test_torn_last_log_line_preserved_and_repaired(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
    with (shoot / LOG).open("ab") as stream:
        stream.write(b'{"v":1,"type":"view","view":')
    before = (shoot / LOG).read_bytes()
    with ShootSession(shoot) as resumed:
        assert len(resumed.stack) == 1
        assert resumed.undo()
    assert (shoot / LOG).read_bytes().startswith(before)
    with ShootSession(shoot) as resumed:
        assert not resumed.stack
        assert len(resumed.snapshot().pending) == 1


def test_invalid_middle_log_line_fails_closed(shoot, make_pair):
    make_pair(shoot)
    (shoot / LOG).write_text('not-json\n' + json.dumps({"v": 1, "type": "view", "view": {"mode": "cull", "key": None}}) + '\n')
    before = file_bytes(shoot)
    with pytest.raises(RecoveryError):
        ShootSession(shoot)
    assert file_bytes(shoot) == before


@pytest.mark.parametrize("relative", ["../outside.JPG", "C:/outside.JPG", "/outside.JPG", "..\\outside.JPG"])
def test_log_cannot_move_outside_selected_shoot(shoot, relative):
    record = {"v": 1, "type": "begin", "id": "bad", "key": "bad", "action": "keep",
              "ops": [{"kind": "move", "src": relative, "dst": "01_secilen/a.JPG"}]}
    (shoot / LOG).write_text(json.dumps(record) + "\n")
    with pytest.raises(ConflictError):
        ShootSession(shoot)


def test_root_duplicate_stems_fail_closed(shoot, make_pair):
    make_pair(shoot)
    (shoot / KEPT).mkdir()
    make_pair(shoot / KEPT)
    with pytest.raises(ConflictError):
        ShootSession(shoot)


def test_stale_photo_cannot_decide_twice(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        photo = session.snapshot().pending[0]
        session.decide(photo, True)
        with pytest.raises(ConflictError):
            session.decide(photo, False)


def test_collision_created_after_preflight_and_recovery(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    real = core.move_no_replace

    def create_racing_target(source, target):
        target.write_bytes(b"external racing writer")
        real(source, target)

    with ShootSession(shoot) as session:
        monkeypatch.setattr(core, "move_no_replace", create_racing_target)
        with pytest.raises(OSError):
            session.decide(session.snapshot().pending[0], True)
        assert (shoot / "IMG_1234.JPG").exists()
        assert (shoot / KEPT / "IMG_1234.JPG").read_bytes() == b"external racing writer"
        assert session.pending_id
    monkeypatch.setattr(core, "move_no_replace", real)
    with pytest.raises(ConflictError):
        ShootSession(shoot)
    # Preserve the external file, free the collision, and recover the transaction.
    real(shoot / KEPT / "IMG_1234.JPG", shoot / "external-file.bin")
    with ShootSession(shoot) as session:
        assert len(session.snapshot().kept) == 1
        assert session.undo()
        assert (shoot / "external-file.bin").read_bytes() == b"external racing writer"


def test_journal_flush_failure_blocks_decisions_until_restart(shoot, make_pair, monkeypatch):
    make_pair(shoot)
    real = core.os.fsync
    with ShootSession(shoot) as session:
        def flush_failure(_):
            raise OSError("simulated disk full / failed log flush")
        monkeypatch.setattr(core.os, "fsync", flush_failure)
        with pytest.raises(OSError):
            session.decide(session.snapshot().pending[0], True)
        assert session.faulted
        assert (shoot / "IMG_1234.JPG").exists()
        with pytest.raises(RecoveryError):
            session.decide(session.snapshot().pending[0], False)
        monkeypatch.setattr(core.os, "fsync", real)
    with ShootSession(shoot) as session:
        assert len(session.snapshot().kept) == 1
        assert session.undo()


def test_torn_tail_ending_in_newline_is_repaired(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot):
        pass
    with (shoot / LOG).open("ab") as stream:
        stream.write(b'{"v":1,"type":"view"\n')
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
    with ShootSession(shoot) as session:
        assert session.undo()


def test_second_crash_during_tail_repair_is_recoverable(shoot, make_pair):
    make_pair(shoot)
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
    with (shoot / LOG).open("ab") as stream:
        stream.write(b'{"v":1,"type":"view"\n{"v":1,"type":"repair"')
    with ShootSession(shoot) as session:
        assert session.undo()
    with ShootSession(shoot) as session:
        assert not session.stack


def test_json_null_in_journal_is_invalid_not_a_torn_fragment(shoot):
    (shoot / LOG).write_text('null\n', encoding='utf-8')
    with pytest.raises(RecoveryError):
        ShootSession(shoot)

