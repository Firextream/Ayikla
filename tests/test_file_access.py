import threading

from ayikla.core import move_no_replace
from ayikla.file_access import file_guard


def test_move_waits_for_in_process_reader_and_preserves_contents(tmp_path):
    source, target = tmp_path / "IMG.JPG", tmp_path / "moved.JPG"
    source.write_bytes(b"generated")
    started, done = threading.Event(), threading.Event()
    errors = []
    def move():
        started.set()
        try:
            move_no_replace(source, target)
        except Exception as error:
            errors.append(error)
        finally:
            done.set()
    with file_guard(source):
        worker = threading.Thread(target=move)
        worker.start()
        assert started.wait(1)
        assert not done.wait(.03)
        assert source.read_bytes() == b"generated" and not target.exists()
    assert done.wait(2)
    worker.join()
    assert not errors and target.read_bytes() == b"generated"


def test_guards_are_case_insensitive_and_reentrant_on_windows(tmp_path):
    path = tmp_path / "IMG.JPG"
    with file_guard(path):
        with file_guard(str(path).lower()):
            pass
