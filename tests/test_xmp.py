import xml.etree.ElementTree as ET

import pytest

from ayikla import core
from ayikla.core import ShootSession, ConflictError
from ayikla.preferences import Preferences
from ayikla.xmp import merge, XMP, DM

PACKET = b'''<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   xmlns:xmpDM="http://ns.adobe.com/xmp/1.0/DynamicMedia/"
   xmp:Rating="5" xmp:Label="Blue" xmpDM:pick="0" crs:Exposure2012="+0.70">
   <!-- Preserve this comment and whitespace exactly -->
   <crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012>
  </rdf:Description>
 </rdf:RDF></x:xmpmeta><?xpacket end="w"?>'''


def property_value(packet, namespace, name):
    tree = ET.fromstring(packet)
    key = f"{{{namespace}}}{name}"
    return next((e.attrib[key] for e in tree.iter() if key in e.attrib), None) or tree.findtext(f".//{key}")


def test_lightroom_packet_changes_only_rating_and_pick_bytes():
    result = merge(PACKET, 1)
    assert result == PACKET.replace(b'xmp:Rating="5"', b'xmp:Rating="1"').replace(b'xmpDM:pick="0"', b'xmpDM:pick="1"')
    assert property_value(result, XMP, "Label") == "Blue"


@pytest.mark.parametrize("packet", [
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>',
    b'<r:RDF xmlns:r="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><r:Description xmlns:a="http://ns.adobe.com/xap/1.0/"><a:Rating>5</a:Rating></r:Description></r:RDF>',
    None,
])
def test_missing_fields_aliases_and_element_properties(packet):
    result = merge(packet, -1)
    assert property_value(result, XMP, "Rating") == "-1"
    assert property_value(result, DM, "pick") == "-1"


def test_xmp_backup_edit_copy_and_exact_undo_after_restart(shoot, make_pair):
    make_pair(shoot)
    original = shoot / "IMG_1234.xmp"
    original.write_bytes(PACKET)
    with ShootSession(shoot, write_xmp=True) as session:
        session.decide(session.snapshot().pending[0], True)
        assert not original.exists()
        assert any(p.read_bytes() == PACKET for p in (shoot / core.ARCHIVE).rglob("*.xmp"))
        kept = session.snapshot().kept[0]
        assert property_value(kept.raw.with_suffix(".xmp").read_bytes(), XMP, "Rating") == "1"
        session.toggle_edit(kept)
        assert property_value((shoot / core.EDIT / original.name).read_bytes(), XMP, "Rating") == "3"
        assert property_value(kept.raw.with_suffix(".xmp").read_bytes(), XMP, "Rating") == "1"
        session.toggle_edit(kept)
        assert not (shoot / core.EDIT / original.name).exists()
    with ShootSession(shoot, write_xmp=False) as session:
        session.undo()  # Undo works even with the setting now disabled.
        assert (shoot / core.EDIT / original.name).exists()
        session.undo()
        session.undo()
        assert original.read_bytes() == PACKET
        assert (shoot / "IMG_1234.JPG").read_bytes().startswith(b"dummy jpeg")


def test_invalid_existing_xmp_does_not_move_photos(shoot, make_pair):
    make_pair(shoot)
    (shoot / "IMG_1234.xmp").write_bytes(b"invalid XML")
    with ShootSession(shoot, write_xmp=True) as session:
        with pytest.raises(ConflictError, match="Cannot merge"):
            session.decide(session.snapshot().pending[0], True)
        assert (shoot / "IMG_1234.JPG").exists()
        assert not session.stack


@pytest.mark.parametrize("boundary", range(5))
def test_xmp_interrupted_write_or_undo_recovers(shoot, make_pair, monkeypatch, boundary):
    make_pair(shoot)
    (shoot / "IMG_1234.xmp").write_bytes(PACKET)
    with ShootSession(shoot, write_xmp=True) as session:
        session.decide(session.snapshot().pending[0], True)
        original_append = session._append
        calls = []
        def interrupt(record):
            if record["type"] in {"applied", "commit"}:
                if len(calls) == boundary:
                    raise OSError("interrupted at checkpoint")
                calls.append(record)
            original_append(record)
        monkeypatch.setattr(session, "_append", interrupt)
        if boundary < 5:
            with pytest.raises(OSError):
                session.undo()
    with ShootSession(shoot) as session:
        assert not session.pending_id
        assert (shoot / "IMG_1234.xmp").read_bytes() == PACKET
        assert len(session.snapshot().pending) == 1


def test_xmp_setting_default_on_and_persistent(tmp_path):
    p = Preferences(tmp_path)
    assert p.write_xmp
    p.set_xmp(False)
    assert not Preferences(tmp_path).write_xmp
