import pytest

from ayikla.core import RAW_EXTENSIONS, ShootSession, ConflictError, pair_photos, KEPT, EDIT, REJECTED


@pytest.mark.parametrize('extension', sorted(RAW_EXTENSIONS))
def test_camera_pair_decisions_edit_resume_undo(shoot, extension):
    jpeg = shoot / 'DSC_001.JpG'
    raw = shoot / ('dsc_001' + extension.upper())
    jpeg.write_bytes(b'generated jpeg')
    raw.write_bytes(b'generated opaque raw')
    helper = shoot / ('._dsc_001' + extension)
    helper.write_bytes(b'metadata')
    with ShootSession(shoot) as session:
        assert len(session.snapshot().pending) == 1
        photo = session.snapshot().pending[0]
        assert photo.raw == raw
        session.decide(photo, False)
        assert (shoot / REJECTED / raw.name).read_bytes() == b'generated opaque raw'
        session.undo()
        session.decide(session.snapshot().pending[0], True)
        kept = session.snapshot().kept[0]
        assert kept.raw.suffix.casefold() == extension
        session.toggle_edit(kept)
    with ShootSession(shoot) as session:
        assert session.snapshot().kept[0].raw.name == raw.name
        assert (shoot / EDIT / raw.name).read_bytes() == b'generated opaque raw'
        session.toggle_edit(session.snapshot().kept[0])
        assert not (shoot / EDIT / raw.name).exists()
        session.undo()
        session.undo()
        session.undo()
        assert jpeg.exists() and raw.exists()
        assert helper.read_bytes() == b'metadata'


@pytest.mark.parametrize('extension', ['.RAF', '.ARW', '.ORF'])
def test_new_partner_and_no_overwrite(shoot, extension):
    (shoot / 'IMG.JPG').write_bytes(b'jpeg')
    with ShootSession(shoot) as session:
        (shoot / ('IMG' + extension)).write_bytes(b'raw')
        with pytest.raises(ConflictError, match='RAW partner'):
            session.decide(session.snapshot().pending[0], True)
        (shoot / KEPT).mkdir(exist_ok=True)
        target = shoot / KEPT / ('IMG' + extension)
        target.write_bytes(b'untouched')
        with pytest.raises(ConflictError):
            session.decide(session.snapshot().pending[0], True)
        assert target.read_bytes() == b'untouched'
        assert (shoot / 'IMG.JPG').exists()


def test_multiple_raw_formats_are_ambiguous(shoot):
    for name in ['IMG.JPG', 'IMG.ARW', 'img.DNG', '._IMG.ORF']:
        (shoot / name).write_bytes(b'dummy')
    with pytest.raises(ConflictError, match='Multiple'):
        pair_photos(shoot)
